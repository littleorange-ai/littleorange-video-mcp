#!/usr/bin/env python3
"""Refresh the packaged api_catalog.json from Apifox docs."""

import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from littleorange_video_mcp.catalog import refresh_catalog_from_apifox, _write_catalog_cache, _load_packaged_catalog_data

def main():
    print("=== 从 Apifox 刷新目录 ===")
    
    # Path to the packaged catalog
    packaged_catalog_path = project_root / "littleorange_video_mcp" / "api_catalog.json"
    
    # Refresh from Apifox
    print("正在从 Apifox 获取最新文档...")
    fresh_data = refresh_catalog_from_apifox()
    
    print(f"\n成功获取: {len(fresh_data['operations'])} 个操作")
    print(f"SHA256: {fresh_data['sha256']}")
    
    # Backup old one
    if packaged_catalog_path.exists():
        backup_path = packaged_catalog_path.with_suffix(".json.bak")
        print(f"\n备份旧文件到: {backup_path}")
        packaged_catalog_path.rename(backup_path)
    
    # Save new one (without the metadata fields we don't need)
    # Keep only the essential fields for the packaged catalog
    minimal_data = {
        "operations": fresh_data["operations"]
    }
    
    print(f"\n写入新目录到: {packaged_catalog_path}")
    with packaged_catalog_path.open("w", encoding="utf-8") as f:
        json.dump(minimal_data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    
    print("\n✅ 完成！api_catalog.json 已更新")
    print("\n提示: 记得提交这个文件到 git")

if __name__ == "__main__":
    main()

