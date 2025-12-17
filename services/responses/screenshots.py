"""Screenshot capture and storage management for computer use."""

import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import base64
import hashlib


class ScreenshotManager:
    """Manages screenshot capture, storage, and retention."""

    def __init__(
        self,
        save_path: str = "./logs/screenshots",
        save_to_disk: bool = True,
        format: str = "png",
        retention_days: int = 7,
        max_size_mb: int = 1000,
        include_timestamp: bool = True,
    ):
        """Initialize screenshot manager.

        Args:
            save_path: Directory to save screenshots
            save_to_disk: Whether to save screenshots to disk
            format: Image format (png, jpeg)
            retention_days: Days to retain screenshots
            max_size_mb: Maximum total storage size in MB
            include_timestamp: Include timestamp in filename
        """
        self.save_path = Path(save_path)
        self.save_to_disk = save_to_disk
        self.format = format
        self.retention_days = retention_days
        self.max_size_mb = max_size_mb
        self.include_timestamp = include_timestamp

        # Create save directory if needed
        if self.save_to_disk:
            self.save_path.mkdir(parents=True, exist_ok=True)

        # In-memory cache for recent screenshots
        self._screenshot_cache: Dict[str, Dict[str, Any]] = {}

    async def capture_screenshot(
        self,
        screenshot_data: str,
        action_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process and store a screenshot.

        Args:
            screenshot_data: Base64 encoded screenshot data or file path
            action_type: Type of action that triggered screenshot
            metadata: Additional metadata to store

        Returns:
            Dictionary with screenshot info
        """
        timestamp = datetime.now()
        screenshot_id = self._generate_screenshot_id(timestamp, action_type)

        screenshot_info = {
            "id": screenshot_id,
            "timestamp": timestamp.isoformat(),
            "action_type": action_type,
            "format": self.format,
            "metadata": metadata or {},
        }

        # Save to disk if enabled
        if self.save_to_disk:
            file_path = await self._save_to_disk(
                screenshot_data,
                screenshot_id,
                timestamp
            )
            screenshot_info["file_path"] = str(file_path)
            screenshot_info["size_bytes"] = file_path.stat().st_size
        else:
            screenshot_info["data"] = screenshot_data

        # Add to cache
        self._screenshot_cache[screenshot_id] = screenshot_info

        # Clean up old screenshots if needed
        await self._cleanup_old_screenshots()

        return screenshot_info

    async def get_screenshot(
        self,
        screenshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve screenshot by ID.

        Args:
            screenshot_id: Screenshot identifier

        Returns:
            Screenshot info or None if not found
        """
        # Check cache first
        if screenshot_id in self._screenshot_cache:
            return self._screenshot_cache[screenshot_id]

        # Try to load from disk
        if self.save_to_disk:
            return await self._load_from_disk(screenshot_id)

        return None

    async def get_recent_screenshots(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get most recent screenshots.

        Args:
            limit: Maximum number of screenshots to return

        Returns:
            List of screenshot info dictionaries
        """
        screenshots = list(self._screenshot_cache.values())

        # Sort by timestamp descending
        screenshots.sort(
            key=lambda x: x["timestamp"],
            reverse=True
        )

        return screenshots[:limit]

    async def delete_screenshot(self, screenshot_id: str) -> bool:
        """Delete a screenshot.

        Args:
            screenshot_id: Screenshot identifier

        Returns:
            True if deleted successfully
        """
        # Remove from cache
        if screenshot_id in self._screenshot_cache:
            screenshot_info = self._screenshot_cache.pop(screenshot_id)

            # Delete file if exists
            if self.save_to_disk and "file_path" in screenshot_info:
                try:
                    Path(screenshot_info["file_path"]).unlink()
                    return True
                except FileNotFoundError:
                    pass

        return False

    async def cleanup_all(self) -> int:
        """Clean up all screenshots.

        Returns:
            Number of screenshots deleted
        """
        count = 0

        if self.save_to_disk:
            # Delete all files in save directory
            for file_path in self.save_path.glob(f"*.{self.format}"):
                try:
                    file_path.unlink()
                    count += 1
                except Exception:
                    pass

        # Clear cache
        self._screenshot_cache.clear()

        return count

    def _generate_screenshot_id(
        self,
        timestamp: datetime,
        action_type: str
    ) -> str:
        """Generate unique screenshot ID.

        Args:
            timestamp: Screenshot timestamp
            action_type: Action type

        Returns:
            Screenshot identifier
        """
        # Create hash from timestamp and action type
        data = f"{timestamp.isoformat()}-{action_type}"
        hash_value = hashlib.md5(data.encode()).hexdigest()[:8]

        if self.include_timestamp:
            ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
            return f"screenshot_{ts_str}_{action_type}_{hash_value}"
        else:
            return f"screenshot_{action_type}_{hash_value}"

    async def _save_to_disk(
        self,
        screenshot_data: str,
        screenshot_id: str,
        timestamp: datetime
    ) -> Path:
        """Save screenshot to disk.

        Args:
            screenshot_data: Base64 encoded data or file path
            screenshot_id: Screenshot identifier
            timestamp: Timestamp

        Returns:
            Path to saved file
        """
        file_name = f"{screenshot_id}.{self.format}"
        file_path = self.save_path / file_name

        # If data is already a file path, just copy it
        if screenshot_data.startswith('/') or screenshot_data.startswith('./'):
            source_path = Path(screenshot_data)
            if source_path.exists():
                import shutil
                shutil.copy(source_path, file_path)
                return file_path

        # Otherwise, decode base64 and save
        try:
            # Remove data URL prefix if present
            if ',' in screenshot_data:
                screenshot_data = screenshot_data.split(',', 1)[1]

            image_bytes = base64.b64decode(screenshot_data)

            async with asyncio.Lock():
                with open(file_path, 'wb') as f:
                    f.write(image_bytes)

        except Exception as e:
            raise Exception(f"Failed to save screenshot: {e}")

        return file_path

    async def _load_from_disk(
        self,
        screenshot_id: str
    ) -> Optional[Dict[str, Any]]:
        """Load screenshot from disk.

        Args:
            screenshot_id: Screenshot identifier

        Returns:
            Screenshot info or None
        """
        file_name = f"{screenshot_id}.{self.format}"
        file_path = self.save_path / file_name

        if not file_path.exists():
            return None

        stat_info = file_path.stat()

        return {
            "id": screenshot_id,
            "file_path": str(file_path),
            "size_bytes": stat_info.st_size,
            "timestamp": datetime.fromtimestamp(stat_info.st_mtime).isoformat(),
            "format": self.format,
        }

    async def _cleanup_old_screenshots(self) -> None:
        """Remove screenshots older than retention period."""
        if not self.save_to_disk:
            return

        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        # Check disk usage
        total_size = sum(
            f.stat().st_size
            for f in self.save_path.glob(f"*.{self.format}")
        )
        total_size_mb = total_size / (1024 * 1024)

        # Clean up if over size limit or past retention
        if total_size_mb > self.max_size_mb:
            # Delete oldest screenshots first
            files = sorted(
                self.save_path.glob(f"*.{self.format}"),
                key=lambda x: x.stat().st_mtime
            )

            for file_path in files:
                file_date = datetime.fromtimestamp(file_path.stat().st_mtime)

                # Delete if old or over size limit
                if file_date < cutoff_date or total_size_mb > self.max_size_mb:
                    try:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        file_path.unlink()
                        total_size_mb -= size_mb

                        # Remove from cache
                        screenshot_id = file_path.stem
                        self._screenshot_cache.pop(screenshot_id, None)

                    except Exception:
                        pass

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.

        Returns:
            Dictionary with storage stats
        """
        if not self.save_to_disk:
            return {
                "total_screenshots": len(self._screenshot_cache),
                "storage_enabled": False,
            }

        files = list(self.save_path.glob(f"*.{self.format}"))
        total_size = sum(f.stat().st_size for f in files)

        return {
            "total_screenshots": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": self.max_size_mb,
            "storage_path": str(self.save_path),
            "retention_days": self.retention_days,
            "cached_screenshots": len(self._screenshot_cache),
        }
