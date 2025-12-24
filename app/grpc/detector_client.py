"""gRPC client for Core/Detector service."""

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator

import grpc
from loguru import logger

from app.core.config import get_settings
from app.grpc import autocare_pb2, autocare_pb2_grpc

settings = get_settings()


@dataclass
class InferenceStatus:
    """Inference status from gRPC."""
    status: int  # NG=0, READY=1, CONNECTING=2, CONNECTED=3
    count: int
    eos: bool
    err: bool
    image: bytes | None = None
    meta: str | None = None


@dataclass
class StreamingResult:
    """Streaming result from gRPC."""
    location: str
    ts_start: int
    session_id: str


@dataclass
class AppInfo:
    """App information from gRPC."""
    id: str
    name: str
    desc: str
    version: str | None = None
    framework: str | None = None
    memory_usage: int | None = None


@dataclass
class DxInfo:
    """DX system information from gRPC."""
    id: str
    name: str
    address: str
    capacity: int
    activated: int
    version: str
    framework: str
    lic_type: str
    lic_end_date: str
    lic_key: str


class DetectorClient:
    """
    gRPC client for Core/Detector service.

    Communicates with the C++ DeepStream inference engine (Core)
    for managing inference pipelines and streaming.
    """

    def __init__(self, address: str | None = None):
        self.address = address or settings.core_grpc_server
        self._channel: grpc.aio.Channel | None = None
        self._stub: autocare_pb2_grpc.DetectorStub | None = None

    async def connect(self) -> None:
        """Connect to gRPC server."""
        try:
            # Create async channel with retry policy
            self._channel = grpc.aio.insecure_channel(
                self.address,
                options=[
                    ("grpc.enable_retries", 1),
                    ("grpc.service_config", self._get_service_config()),
                    ("grpc.max_receive_message_length", 100 * 1024 * 1024),  # 100MB
                    ("grpc.max_send_message_length", 100 * 1024 * 1024),  # 100MB
                ],
            )
            self._stub = autocare_pb2_grpc.DetectorStub(self._channel)
            logger.info(f"Connected to gRPC at {self.address}")
        except Exception as e:
            logger.error(f"Failed to connect to gRPC: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from gRPC server."""
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("Disconnected from gRPC")

    def _get_service_config(self) -> str:
        """Get gRPC service config with retry policy."""
        return json.dumps({
            "methodConfig": [{
                "name": [{"service": "autocare.Detector"}],
                "retryPolicy": {
                    "maxAttempts": 100,
                    "initialBackoff": "5s",
                    "maxBackoff": "60s",
                    "backoffMultiplier": 2,
                    "retryableStatusCodes": ["UNAVAILABLE"]
                }
            }]
        })

    def _ensure_connected(self) -> None:
        """Ensure client is connected."""
        if self._stub is None:
            raise RuntimeError("gRPC client is not connected. Call connect() first.")

    async def add_inference(
        self,
        app_id: str,
        video_id: str,
        uri: str,
        settings: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> int:
        """
        Add inference configuration to Core.

        Args:
            app_id: Application ID
            video_id: Video/stream ID
            uri: RTSP URI of the video stream
            settings: Optional inference settings as dict (will be JSON serialized)
            name: Optional inference name

        Returns:
            Count from response (number of affected inferences)
        """
        self._ensure_connected()

        request = autocare_pb2.InferenceReq(
            app_id=app_id,
            stream_id=video_id,
            uri=uri,
        )

        if settings:
            request.settings = json.dumps(settings)
        if name:
            request.name = name

        try:
            response: autocare_pb2.InferenceRes = await self._stub.AddInference(request)
            logger.info(f"gRPC AddInference: app={app_id}, video={video_id}, count={response.count}")
            return response.count
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC AddInference failed: {e.code()} - {e.details()}")
            raise

    async def remove_inference(
        self,
        app_id: str,
        video_id: str,
    ) -> int:
        """
        Remove inference configuration from Core.

        Returns:
            Count from response (number of affected inferences)
        """
        self._ensure_connected()

        request = autocare_pb2.InferenceReq(
            app_id=app_id,
            stream_id=video_id,
        )

        try:
            response: autocare_pb2.InferenceRes = await self._stub.RemoveInference(request)
            logger.info(f"gRPC RemoveInference: app={app_id}, video={video_id}, count={response.count}")
            return response.count
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC RemoveInference failed: {e.code()} - {e.details()}")
            raise

    async def remove_inference_all(self, app_id: str) -> bool:
        """Remove all inferences for an app."""
        self._ensure_connected()

        request = autocare_pb2.AppReq(app_id=app_id)

        try:
            response: autocare_pb2.AppRes = await self._stub.RemoveInferenceAll(request)
            logger.info(f"gRPC RemoveInferenceAll: app={app_id}, result={response.result}")
            return response.result
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC RemoveInferenceAll failed: {e.code()} - {e.details()}")
            raise

    async def update_inference(
        self,
        app_id: str,
        video_id: str,
        settings: dict[str, Any] | None = None,
        name: str | None = None,
    ) -> int:
        """
        Update inference configuration in Core.

        Returns:
            Count from response (number of affected inferences)
        """
        self._ensure_connected()

        request = autocare_pb2.InferenceReq(
            app_id=app_id,
            stream_id=video_id,
        )

        if settings:
            request.settings = json.dumps(settings)
        if name:
            request.name = name

        try:
            response: autocare_pb2.InferenceRes = await self._stub.UpdateInference(request)
            logger.info(f"gRPC UpdateInference: app={app_id}, video={video_id}, count={response.count}")
            return response.count
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC UpdateInference failed: {e.code()} - {e.details()}")
            raise

    async def get_inference_status(
        self,
        app_id: str,
        video_id: str,
    ) -> InferenceStatus | None:
        """
        Get inference status from Core.

        Returns:
            InferenceStatus with status code:
            - 0: NG (Not Good/Error)
            - 1: READY
            - 2: CONNECTING
            - 3: CONNECTED
        """
        self._ensure_connected()

        request = autocare_pb2.InferenceReq(
            app_id=app_id,
            stream_id=video_id,
        )

        try:
            response: autocare_pb2.InferenceRes = await self._stub.GetInferenceStatus(request)
            return InferenceStatus(
                status=response.status if response.HasField("status") else 0,
                count=response.count,
                eos=response.eos if response.HasField("eos") else False,
                err=response.err if response.HasField("err") else False,
                meta=response.meta if response.HasField("meta") else None,
            )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC GetInferenceStatus failed: {e.code()} - {e.details()}")
            return None

    async def get_inference_status_all(self, app_id: str | None = None) -> list[InferenceStatus]:
        """Get all inference statuses for an app (or all apps if app_id is None)."""
        self._ensure_connected()

        request = autocare_pb2.AppReq()
        if app_id:
            request.app_id = app_id

        try:
            response: autocare_pb2.InferenceResList = await self._stub.GetInferenceStatusAll(request)
            return [
                InferenceStatus(
                    status=inf.status if inf.HasField("status") else 0,
                    count=inf.count,
                    eos=inf.eos if inf.HasField("eos") else False,
                    err=inf.err if inf.HasField("err") else False,
                    meta=inf.meta if inf.HasField("meta") else None,
                )
                for inf in response.inference
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC GetInferenceStatusAll failed: {e.code()} - {e.details()}")
            return []

    async def request_preview_image(
        self,
        app_id: str,
        video_id: str,
    ) -> InferenceStatus | None:
        """
        Request preview/snapshot image from Core.

        Returns:
            InferenceStatus with image bytes in the image field
        """
        self._ensure_connected()

        request = autocare_pb2.InferenceReq(
            app_id=app_id,
            stream_id=video_id,
        )

        try:
            response: autocare_pb2.InferenceRes = await self._stub.RequestPreviewImage(request)
            return InferenceStatus(
                status=response.status if response.HasField("status") else 0,
                count=response.count,
                eos=response.eos if response.HasField("eos") else False,
                err=response.err if response.HasField("err") else False,
                image=response.snapshot if response.HasField("snapshot") else None,
                meta=response.meta if response.HasField("meta") else None,
            )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC RequestPreviewImage failed: {e.code()} - {e.details()}")
            return None

    async def start_streaming(
        self,
        uri: str,
        session_id: str | None = None,
    ) -> StreamingResult | None:
        """
        Start HLS streaming from Core.

        Args:
            uri: RTSP URI to stream
            session_id: Optional session ID for tracking

        Returns:
            StreamingResult with HLS location and timestamps
        """
        self._ensure_connected()

        request = autocare_pb2.StreamingReq(uri=uri)
        if session_id:
            request.session_id = session_id

        try:
            response: autocare_pb2.StreamingRes = await self._stub.StartStreaming(request)
            return StreamingResult(
                location=response.location if response.HasField("location") else "",
                ts_start=response.ts_start if response.HasField("ts_start") else 0,
                session_id=response.session_id if response.HasField("session_id") else "",
            )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC StartStreaming failed: {e.code()} - {e.details()}")
            return None

    async def stop_streaming(self, session_id: str) -> bool:
        """Stop HLS streaming in Core."""
        self._ensure_connected()

        request = autocare_pb2.StreamingReq(session_id=session_id)

        try:
            await self._stub.StopStreaming(request)
            logger.info(f"gRPC StopStreaming: session={session_id}")
            return True
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC StopStreaming failed: {e.code()} - {e.details()}")
            return False

    async def install_app(self, app_data: bytes, app_id: str | None = None) -> bool:
        """
        Install app package in Core via streaming.

        Args:
            app_data: App package bytes (tar.gz)
            app_id: Optional app ID

        Returns:
            True if installation succeeded
        """
        self._ensure_connected()

        async def chunk_generator() -> AsyncIterator[autocare_pb2.AppReq]:
            """Generate chunks for streaming upload."""
            chunk_size = 64 * 1024  # 64KB chunks
            for i in range(0, len(app_data), chunk_size):
                chunk = app_data[i:i + chunk_size]
                request = autocare_pb2.AppReq(chunk=chunk)
                if app_id and i == 0:  # Send app_id with first chunk
                    request.app_id = app_id
                yield request

        try:
            response: autocare_pb2.AppRes = await self._stub.InstallApp(chunk_generator())
            logger.info(f"gRPC InstallApp: size={len(app_data)}, result={response.result}")
            return response.result
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC InstallApp failed: {e.code()} - {e.details()}")
            return False

    async def uninstall_app(self, app_id: str) -> bool:
        """Uninstall app from Core."""
        self._ensure_connected()

        request = autocare_pb2.AppReq(app_id=app_id)

        try:
            response: autocare_pb2.AppRes = await self._stub.UninstallApp(request)
            logger.info(f"gRPC UninstallApp: app={app_id}, result={response.result}")
            return response.result
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC UninstallApp failed: {e.code()} - {e.details()}")
            return False

    async def get_app_list(self) -> list[AppInfo]:
        """Get list of installed apps from Core."""
        self._ensure_connected()

        request = autocare_pb2.AppReq()

        try:
            response: autocare_pb2.AppList = await self._stub.GetAppList(request)
            return [
                AppInfo(
                    id=app.id,
                    name=app.name,
                    desc=app.desc,
                    version=app.version if app.HasField("version") else None,
                    framework=app.framework if app.HasField("framework") else None,
                    memory_usage=app.memory_usage if app.HasField("memory_usage") else None,
                )
                for app in response.app
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC GetAppList failed: {e.code()} - {e.details()}")
            return []

    async def get_inference_list(self, app_id: str | None = None) -> list[dict[str, Any]]:
        """Get list of inferences from Core."""
        self._ensure_connected()

        request = autocare_pb2.InferenceReq()
        if app_id:
            request.app_id = app_id

        try:
            response: autocare_pb2.InferenceList = await self._stub.GetInferenceList(request)
            return [
                {
                    "app_id": inf.app_id,
                    "stream_id": inf.stream_id if inf.HasField("stream_id") else None,
                    "uri": inf.uri if inf.HasField("uri") else None,
                    "settings": inf.settings if inf.HasField("settings") else None,
                    "name": inf.name if inf.HasField("name") else None,
                }
                for inf in response.inference
            ]
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC GetInferenceList failed: {e.code()} - {e.details()}")
            return []

    async def get_dx_info(self) -> DxInfo | None:
        """Get DX system info from Core."""
        self._ensure_connected()

        request = autocare_pb2.Empty()

        try:
            response: autocare_pb2.Dx = await self._stub.GetDx(request)
            return DxInfo(
                id=response.id,
                name=response.name,
                address=response.address,
                capacity=response.capacity,
                activated=response.activated,
                version=response.version,
                framework=response.framework,
                lic_type=response.lic_type,
                lic_end_date=response.lic_end_date,
                lic_key=response.lic_key,
            )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC GetDx failed: {e.code()} - {e.details()}")
            return None

    async def license_activation(
        self,
        license_key: str,
        hash_code: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Request license activation (.req file generation).

        Args:
            license_key: License key
            hash_code: Optional hash code

        Returns:
            Tuple of (success, hash_code)
        """
        self._ensure_connected()

        request = autocare_pb2.LicReq(key=license_key)
        if hash_code:
            request.hash_code = hash_code

        try:
            response: autocare_pb2.LicRes = await self._stub.LicenseActivation(request)
            return response.result, response.hash_code if response.HasField("hash_code") else None
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC LicenseActivation failed: {e.code()} - {e.details()}")
            return False, None

    async def license_deactivation(
        self,
        license_key: str,
        hash_code: str | None = None,
    ) -> tuple[bool, str | None]:
        """
        Request license deactivation.

        Args:
            license_key: License key
            hash_code: Optional hash code

        Returns:
            Tuple of (success, hash_code)
        """
        self._ensure_connected()

        request = autocare_pb2.LicReq(key=license_key)
        if hash_code:
            request.hash_code = hash_code

        try:
            response: autocare_pb2.LicRes = await self._stub.LicenseDeactivation(request)
            return response.result, response.hash_code if response.HasField("hash_code") else None
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC LicenseDeactivation failed: {e.code()} - {e.details()}")
            return False, None

    async def license_activate(
        self,
        license_key: str,
        hash_code: str | None = None,
    ) -> bool:
        """
        Activate license (.lic file application).

        Args:
            license_key: License key
            hash_code: Optional hash code from activation

        Returns:
            True if activation succeeded
        """
        self._ensure_connected()

        request = autocare_pb2.LicReq(key=license_key)
        if hash_code:
            request.hash_code = hash_code

        try:
            response: autocare_pb2.LicRes = await self._stub.LicenseActivate(request)
            return response.result
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC LicenseActivate failed: {e.code()} - {e.details()}")
            return False
