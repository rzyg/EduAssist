import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from core.allowance.utils.modules import DayData
from core.config import DATA_DIR


def _download_holiday_data(year: int) -> None:
    """
    下载指定年份的节假日数据。
    :param year: 年份，格式为 "YYYY"
    :return:
    """
    base_url = "https://timor.tech/api/holiday/year/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    with httpx.Client(follow_redirects=True) as client:
        response = client.get(f"{base_url}{year}?week=Y", headers=headers)

    # 使用 Path 处理路径
    save_dir = Path(DATA_DIR) / "holiday"
    save_dir.mkdir(parents=True, exist_ok=True)  # 自动创建目录

    save_file = save_dir / f"{year}.json"

    if response.status_code == 200:
        save_file.write_text(response.text, encoding="utf-8")
        logger.info(f"✅ 文件已保存: {save_file}")
    else:
        logger.error(f"❌ 请求失败，状态码: {response.status_code}")


def get_holiday_data(year: int):
    """
    获取指定年份的节假日数据。

    Args:
        year (str): 年份，格式为 "YYYY"

    Returns:
        List[DayData]: 包含所有节假日数据的列表，每个元素都是一个 DayData 对象

    Raises:
        FileNotFoundError: 文件不存在时抛出
        json.JSONDecodeError: JSON 格式错误时抛出
        KeyError: 缺少必要字段时抛出
    """
    file_path = Path(DATA_DIR) / "holiday" / f"{year}.json"
    if not file_path.exists():
        _download_holiday_data(year)
    results = _init_holiday_data(file_path)
    return results


def _init_holiday_data(file_path: Path) -> list[DayData]:
    """
    从 JSON 文件加载节假日数据，返回 DayData 对象列表。

    Args:
        file_path (str): JSON 文件的路径

    Returns:
        List[DayData]: 包含所有节假日数据的列表，每个元素都是一个 DayData 对象

    Raises:
        FileNotFoundError: 文件不存在时抛出
        json.JSONDecodeError: JSON 格式错误时抛出
        KeyError: 缺少必要字段时抛出
    """
    with open(file_path, "r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    holiday_dict: dict[str, Any] = data.get("holiday", {})
    result: list[DayData] = []

    for key, item in holiday_dict.items():
        # 提取必要字段
        is_holiday: bool = item.get("holiday", False)  # 默认非节假日
        name: str = item.get("name", "")
        date_str: str = item.get("date", "")
        # after 字段可选，不存在则默认为 False
        after: bool = item.get("after", False)

        # 转换日期字符串为 date 对象
        if not date_str:
            # 若 date 字段缺失，可根据 key (MM-DD) 和当前年份构建，但示例中已提供，故跳过
            raise ValueError(f"Missing 'date' field for entry {key}")
        date_obj: date = date.fromisoformat(date_str)

        # 实例化 DayData
        day_data = DayData(holiday=is_holiday, date=date_obj, name=name, after=after)
        result.append(day_data)

    return result
