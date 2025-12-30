"""Inference service for inference configuration management."""

from pathlib import Path

from loguru import logger
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.inference import Inference
from app.schemas.inference import (
    InferenceCreate,
    InferenceDTO,
    InferenceSettings,
    InferenceWithStatus,
)
from app.services.base_service import BaseService

settings = get_settings()


class InferenceService(BaseService[Inference]):
    """Inference service for inference configuration operations."""

    def __init__(self, db: AsyncSession, grpc_client=None):
        super().__init__(db, Inference)
        self.grpc_client = grpc_client

    async def get_by_composite_key(
        self, app_id: str, video_id: str
    ) -> Inference | None:
        """Get inference by composite key (app_id, video_id)."""
        result = await self.db.execute(
            select(Inference).where(
                and_(
                    Inference.app_id == app_id,
                    Inference.video_id == video_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_by_video_id(self, video_id: str) -> list[InferenceDTO]:
        """Get all inferences for a video."""
        result = await self.db.execute(
            select(Inference).where(Inference.video_id == video_id)
        )
        inferences = result.scalars().all()
        return [self._to_dto(i) for i in inferences]

    async def create_inference(self, data: InferenceCreate) -> InferenceDTO:
        """Create new inference configuration."""
        inference = Inference(
            app_id=data.app_id,
            video_id=data.video_id,
            uri=data.uri,
            name=data.name,
            type=data.type,
        )
        if data.settings:
            inference.set_settings(data.settings.model_dump())
        if data.node_settings:
            inference.set_node_settings(data.node_settings)

        # Register with Core via gRPC
        if self.grpc_client:
            await self.grpc_client.add_inference(
                app_id=data.app_id,
                video_id=data.video_id,
                uri=data.uri,
                settings=data.settings.model_dump() if data.settings else None,
            )

        inference = await self.create(inference)
        return self._to_dto(inference)

    async def remove_inference(self, app_id: str, video_id: str) -> bool:
        """Remove inference configuration."""
        inference = await self.get_by_composite_key(app_id, video_id)
        if not inference:
            return False

        # Unregister from Core via gRPC (best effort - continue even if Core doesn't have it)
        if self.grpc_client:
            try:
                await self.grpc_client.remove_inference(
                    app_id=app_id,
                    video_id=video_id,
                )
            except Exception as e:
                # Core might not have this inference (already removed, never added, etc.)
                logger.warning(f"Failed to remove inference from Core (continuing): {e}")

        await self.delete(inference)
        return True

    async def update_event_setting(
        self,
        app_id: str,
        video_id: str,
        new_settings: InferenceSettings,
        node_settings: str | None = None,
    ) -> tuple[InferenceDTO | None, dict]:
        """Update inference event settings.

        Pipeline:
        1. Validate inference exists in DB
        2. Send to NATS (event-compositor) with request-response
        3. Get terminal event list from compositor
        4. Update DB with new settings
        5. Return DTO and NATS response info

        Returns:
            Tuple of (InferenceDTO or None, nats_response_info dict)
        """
        from app.workers.nats_publisher import EventSettingResponse

        inference = await self.get_by_composite_key(app_id, video_id)
        if not inference:
            return None, {"error": "Inference not found"}

        nats_info: dict = {
            "nats_sent": False,
            "nats_success": False,
            "nats_message": "",
            "term_ev_list": [],
        }

        # Send to NATS (event-compositor) if core services enabled
        if settings.enable_core_services:
            try:
                from app.workers.nats_publisher import get_nats_publisher

                publisher = await get_nats_publisher()

                # Convert to NATS format (camelCase)
                nats_payload = new_settings.to_nats_dict()

                response = await publisher.publish_event_setting_update(
                    app_id=app_id,
                    video_id=video_id,
                    settings=nats_payload,
                )

                nats_info["nats_sent"] = True
                nats_info["nats_success"] = response.success
                nats_info["nats_message"] = response.message
                nats_info["term_ev_list"] = response.term_ev_list

                if not response.success:
                    logger.warning(
                        f"Event compositor rejected settings for {app_id}/{video_id}: "
                        f"{response.message}"
                    )
                    # Continue to save DB anyway - user can retry
            except Exception as e:
                logger.warning(f"Failed to publish event setting update to NATS: {e}")
                nats_info["nats_message"] = str(e)

        # Update gRPC client if available
        if self.grpc_client:
            try:
                await self.grpc_client.update_inference(
                    app_id=app_id,
                    video_id=video_id,
                    settings=new_settings.model_dump(),
                )
            except Exception as e:
                logger.warning(f"Failed to update inference via gRPC: {e}")

        # Always save to DB
        inference.set_settings(new_settings.model_dump())
        if node_settings is not None:
            try:
                import json
                node_settings_dict = json.loads(node_settings)
                inference.set_node_settings(node_settings_dict)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse node_settings JSON for {app_id}/{video_id}")
        await self.update(inference)

        return self._to_dto(inference), nats_info

    async def get_preview_image(
        self, app_id: str, video_id: str
    ) -> bytes | None:
        """Get preview image from Core via gRPC."""
        if not self.grpc_client:
            return None

        result = await self.grpc_client.request_preview_image(
            app_id=app_id,
            video_id=video_id,
        )
        if result and result.image:
            return result.image
        return None

    async def start_stream(
        self, app_id: str, video_id: str, uri: str
    ) -> dict | None:
        """Start streaming via gRPC."""
        if not self.grpc_client:
            return None

        # Generate session ID from app_id and video_id for tracking
        session_id = f"{app_id}_{video_id}"

        result = await self.grpc_client.start_streaming(
            uri=uri,
            session_id=session_id,
        )
        if result:
            return {
                "location": result.location,
                "ts_start": result.ts_start,
                "session_id": result.session_id,
            }
        return None

    async def stop_stream(self, session_id: str) -> bool:
        """Stop streaming via gRPC."""
        if not self.grpc_client:
            return False

        await self.grpc_client.stop_streaming(session_id=session_id)
        return True

    async def get_statuses(self, video_id: str | None = None) -> list[InferenceWithStatus]:
        """Get inference statuses. If video_id is None, returns all."""
        if video_id:
            inferences = await self.get_by_video_id(video_id)
        else:
            inferences = await self.get_all()

        statuses = []
        for inf in inferences:
            status = InferenceWithStatus(
                app_id=inf.app_id,
                video_id=inf.video_id,
                status=0,  # Default to NG
                count=0,
                eos=False,
                err=False,
            )

            # Get status from Core via gRPC
            if self.grpc_client:
                grpc_status = await self.grpc_client.get_inference_status(
                    app_id=inf.app_id,
                    video_id=inf.video_id,
                )
                if grpc_status:
                    status.status = grpc_status.status
                    status.count = grpc_status.count
                    status.eos = grpc_status.eos
                    status.err = grpc_status.err

            statuses.append(status)

        return statuses

    def _to_dto(self, inference: Inference) -> InferenceDTO:
        """Convert Inference model to DTO."""
        settings_dict = inference.get_settings()
        node_settings = inference.get_node_settings()

        return InferenceDTO(
            app_id=inference.app_id,
            video_id=inference.video_id,
            uri=inference.uri,
            name=inference.name,
            type=inference.type,
            settings=InferenceSettings(**settings_dict) if settings_dict else None,
            node_settings=node_settings if node_settings else None,
        )
