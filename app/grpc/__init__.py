"""gRPC client for Core (Detector) communication."""

from app.grpc.detector_client import DetectorClient

# Global gRPC client instance (set by main.py on startup)
_grpc_client: DetectorClient | None = None


def get_grpc_client() -> DetectorClient | None:
    """Get the global gRPC client instance."""
    return _grpc_client


def set_grpc_client(client: DetectorClient | None) -> None:
    """Set the global gRPC client instance."""
    global _grpc_client
    _grpc_client = client


__all__ = [
    "DetectorClient",
    "get_grpc_client",
    "set_grpc_client",
]
