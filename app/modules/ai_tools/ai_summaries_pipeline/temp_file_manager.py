import os
import tempfile
import logging
from typing import Optional
from contextlib import contextmanager

class TempFileManager:
    """
    Utility class that manages temporary files with a context manager.
    Automatically deletes files when they are no longer needed.
    """

    def __init__(self, logger=None):
        """Initialize the temp file manager with optional logger"""
        self.logger = logger or logging.getLogger(__name__)

    @contextmanager
    def temp_file(self, suffix: Optional[str] = None, prefix: Optional[str] = None,
                  dir: Optional[str] = None, text: bool = False):
        """
        Context manager that creates a temporary file and ensures it gets deleted.

        Args:
            suffix: Optional file suffix
            prefix: Optional file prefix
            dir: Optional directory for the temp file
            text: Whether to open the file in text mode

        Yields:
            Tuple[str, file]: The file path and the open file object
        """
        temp_file_handle, temp_file_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir, text=text)
        self.logger.debug(f"Created temporary file: {temp_file_path}")

        try:
            # Convert the file handle to a Python file object for easier use
            temp_file = os.fdopen(temp_file_handle, 'wb+' if not text else 'w+')
            try:
                yield temp_file_path, temp_file
            finally:
                # Close the file if it's still open
                if not temp_file.closed:
                    temp_file.close()
        finally:
            # Delete the file from disk
            try:
                os.unlink(temp_file_path)
                self.logger.debug(f"Deleted temporary file: {temp_file_path}")
            except Exception as e:
                self.logger.warning(f"Failed to delete temporary file {temp_file_path}: {str(e)}")

    @contextmanager
    def temp_directory(self, suffix: Optional[str] = None, prefix: Optional[str] = None,
                      dir: Optional[str] = None):
        """
        Context manager that creates a temporary directory and ensures it gets deleted.

        Args:
            suffix: Optional directory suffix
            prefix: Optional directory prefix
            dir: Optional parent directory

        Yields:
            str: The temporary directory path
        """
        temp_dir = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
        self.logger.debug(f"Created temporary directory: {temp_dir}")

        try:
            yield temp_dir
        finally:
            # Delete the directory and its contents
            try:
                for root, dirs, files in os.walk(temp_dir, topdown=False):
                    for file in files:
                        os.unlink(os.path.join(root, file))
                    for dir_name in dirs:
                        os.rmdir(os.path.join(root, dir_name))
                os.rmdir(temp_dir)
                self.logger.debug(f"Deleted temporary directory: {temp_dir}")
            except Exception as e:
                self.logger.warning(f"Failed to delete temporary directory {temp_dir}: {str(e)}")
