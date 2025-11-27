import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class StorageService:
    """
    Trách nhiệm:
      - Nhận vào path file local (PNG)
      - Trả về URL public (hoặc internal) để lưu vào DB.
    Tạm thời: dùng local/static URL
    Sau này: đổi sang S3 / GCS mà không phải sửa code ở chỗ gọi.
    """

    def __init__(self, base_public_url: str, base_dir: str):
        # VD: base_public_url = "https://report.mycompany.com/static/visual/"
        #     base_dir        = "/var/www/static/visual"
        self.base_public_url = base_public_url.rstrip("/") + "/"
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def upload_file(self, src_path: Path, relative_subdir: Optional[str] = None) -> Optional[str]:
        """
        Tạm thời: copy file từ baseline_dir sang thư mục public, trả về URL.
        Sau này: đổi nội dung hàm này thành upload lên S3.
        """
        try:
            rel_dir = Path(relative_subdir) if relative_subdir else Path("")
            dest_dir = self.base_dir / rel_dir
            dest_dir.mkdir(parents=True, exist_ok=True)

            dest_path = dest_dir / src_path.name
            if src_path.resolve() != dest_path.resolve():
                dest_path.write_bytes(src_path.read_bytes())

            # URL: base_public_url + relative_subdir + filename
            url = self.base_public_url + (str(rel_dir) + "/" if rel_dir else "") + src_path.name
            logger.info(f"[StorageService] Uploaded {src_path} -> {url}")
            return url
        except Exception as e:
            logger.error(f"[StorageService] upload_file lỗi: {e}", exc_info=True)
            return None
