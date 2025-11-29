"""用户输入 /今日简报 获取60秒读懂世界简报"""
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
import aiohttp
import asyncio
import json

# 接口地址
API_URL = "https://know.zousanzy.cn/60/"

@register("今日简报", "egg", "获取走小散的今日简报接口信息", "1.0.0", "")
class NewsPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def get_image_url(self, session):
        """从接口获取图片URL"""
        try:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    # 解析JSON，提取图片路径
                    if isinstance(data, dict) and "images" in data:
                        images = data.get("images", [])
                        if images and len(images) > 0:
                            image_path = images[0].get("path", "")
                            if image_path:
                                return image_path
                return None
        except (aiohttp.ClientError, json.JSONDecodeError, KeyError) as e:
            print(f"获取图片URL失败: {e}")
            return None

    @filter.command("今日简报")
    async def news_command(self, event: AstrMessageEvent):
        '''新闻查询指令，使用格式：/今日简报'''
        yield event.plain_result("正在获取今日简报...")

        async with aiohttp.ClientSession() as session:
            image_url = await self.get_image_url(session)
            if image_url:
                yield event.image_result(image_url)  # 使用从JSON中提取的图片URL
            else:
                yield event.plain_result("无法获取今日简报，请稍后再试。")

    async def terminate(self):
        '''插件卸载时调用'''
        pass

if __name__ == "__main__":
    # 本地测试代码（不依赖 AstrBot）
    async def test():
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    print("JSON数据获取成功:")
                    print(json.dumps(data, indent=2, ensure_ascii=False))
                    if isinstance(data, dict) and "images" in data:
                        images = data.get("images", [])
                        if images and len(images) > 0:
                            image_path = images[0].get("path", "")
                            print(f"\n图片URL: {image_path}")
                else:
                    print("获取失败，状态码:", response.status)

    asyncio.run(test())