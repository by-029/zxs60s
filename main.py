from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
import json
import asyncio
import datetime 
import aiohttp
import os
import tempfile
from zoneinfo import ZoneInfo  # 导入 ZoneInfo 用于处理时区
import chinese_calendar as calendar  # 导入 chinese_calendar 库

@register("zxs60s", "egg", "今日简报插件，支持定时发送", "2.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.enabled = config.get("enabled", True)  # 从配置文件读取今日简报定时任务启用状态
        self.temp_dir = tempfile.mkdtemp()  # 创建临时目录
        self.config = config
        logger.info(f"插件配置信息: {self.config}")
        self.zxs_api_url = config.get("zxs_api_url") or "https://know.zousanzy.cn/60/"
        logger.info(f"当前使用的今日简报API URL: {self.zxs_api_url}")
        self.default_timezone = config.get("default_timezone")
        try:
            self.user_custom_timezone = ZoneInfo(self.default_timezone)
        except Exception:
            self.user_custom_timezone = ZoneInfo('Asia/Shanghai')
        # 使用字典存储多个群组的时间设置，格式：{群组标识: {'time': 'HH:MM', 'target': message_target}}
        self.group_schedules = {}
        # 获取当前脚本所在目录
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        # 将 schedule.json 存储在插件目录
        self.schedule_file = os.path.join(plugin_dir, 'schedule.json')
        self.load_schedule()
        asyncio.get_event_loop().create_task(self.scheduled_task()) 
        
    def get_group_id(self, message_target):
        """将消息目标转换为可序列化的群组标识"""
        # 尝试获取群组ID，如果无法获取则使用字符串表示
        try:
            # 假设 message_target 有某种标识属性，这里需要根据实际API调整
            if hasattr(message_target, '__str__'):
                return str(message_target)
            return str(message_target)
        except:
            return str(message_target)
    
    def load_schedule(self):
        if not self.enabled:
            logger.info("定时任务已禁用，不加载定时任务信息。")
            return
        '''加载定时任务信息'''
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 兼容旧版本格式
                    if 'group_schedules' in data:
                        # 新格式：多群组支持
                        schedules = data.get('group_schedules', {})
                        self.group_schedules = {}
                        # 注意：message_target 对象无法直接序列化，需要在运行时重新设置
                        # 这里只加载时间信息，target 需要在 set_time 时重新设置
                        for group_id, schedule_info in schedules.items():
                            self.group_schedules[group_id] = {
                                'time': schedule_info.get('time'),
                                'target': None  # 需要在运行时重新设置
                            }
                    else:
                        # 旧格式兼容：转换为新格式
                        old_time = data.get('user_custom_time')
                        old_target = data.get('message_target')
                        if old_time and old_target:
                            group_id = self.get_group_id(old_target)
                            self.group_schedules = {
                                group_id: {
                                    'time': old_time,
                                    'target': None
                                }
                            }
                
                if self.group_schedules:
                    now = datetime.datetime.now(self.user_custom_timezone)
                    logger.info(f"读取定时任务，共 {len(self.group_schedules)} 个群组设置了发送时间")

            except Exception as e:
                logger.error(f"加载定时任务信息失败: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")

    def save_schedule(self):
        # 保存多群组时间设置，注意：message_target 对象无法序列化，只保存时间
        schedules_to_save = {}
        for group_id, schedule_info in self.group_schedules.items():
            schedules_to_save[group_id] = {
                'time': schedule_info.get('time')
            }
        data = {
            'group_schedules': schedules_to_save
        }
        try:
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存定时任务信息失败: {e}")
            import traceback
            logger.error(f"错误详情: {traceback.format_exc()}")

    async def get_zxs_image_url(self, session):
        """从接口获取今日简报图片URL"""
        try:
            async with session.get(self.zxs_api_url) as response:
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
            logger.error(f"获取今日简报图片URL失败: {e}")
            return None
    
    async def get_zxs_image(self):
        '''获取今日简报图片URL或本地路径'''
        try:
            async with aiohttp.ClientSession() as session:
                image_url = await self.get_zxs_image_url(session)
                if image_url:
                    # 下载图片到临时文件
                    try:
                        async with session.get(image_url) as res:
                            if res.status == 200:
                                image_data = await res.read()
                                temp_path = os.path.join(self.temp_dir, 'zxs60s.jpg')
                                with open(temp_path, 'wb') as f:
                                    f.write(image_data)
                                return temp_path
                    except Exception as e:
                        logger.error(f"下载今日简报图片失败: {e}")
                        # 如果下载失败，返回URL让调用者处理
                        return image_url
                return None
        except Exception as e:
            logger.error(f"获取今日简报图片时出错: {e.__class__.__name__}: {str(e)}")
            return None

    def parse_time(self, time: str):
        try:
            # 尝试处理 HH:MM 格式
            hour, minute = map(int, time.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                return None
            return f"{hour:02d}:{minute:02d}"
        except ValueError:
            try:
                # 如果用户输入的时间格式为 HHMM
                if len(time) == 4:
                    hour = int(time[:2])
                    minute = int(time[2:])
                    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                        return None
                    return f"{hour:02d}:{minute:02d}"
            except ValueError:
                return None

    @filter.command("zxs_time")
    async def set_time(self, event: AstrMessageEvent, time: str):
        '''设置发送今日简报的时间 格式为 HH:MM或HHMM'''
        time = time.strip()
        parsed_time = self.parse_time(time)
        if not parsed_time:
            yield event.plain_result("时间格式错误，请输入正确的格式，例如：09:00或0900")
            return
        
        # 获取当前群组标识
        group_id = self.get_group_id(event.unified_msg_origin)
        
        # 为当前群组设置时间
        if group_id not in self.group_schedules:
            self.group_schedules[group_id] = {}
        
        self.group_schedules[group_id]['time'] = parsed_time
        self.group_schedules[group_id]['target'] = event.unified_msg_origin
        
        yield event.plain_result(f"本群组今日简报发送时间已设置为: {parsed_time}")
        self.save_schedule()

    def save_config(self):
        """
        保存配置信息到配置文件
        """
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            # 构建上一级目录的config文件夹路径
            parent_dir = os.path.dirname(current_dir)
            grandparent_dir = os.path.dirname(os.path.dirname(current_dir))
            config_dir = os.path.join(grandparent_dir, 'config')
            # 确保配置目录存在
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            config_file = os.path.join(config_dir, 'astrbot_plugin_moyurenpro_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            # 添加日志记录保存目录
            logger.info(f"配置文件已保存到: {config_file}")
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")

    async def terminate(self):
        """
        关闭定时任务并清理缓存
        """
        # 禁用定时任务
        #self.enabled = False
        #self.config["enabled"] = self.enabled
        #self.save_config()  # 保存配置文件
        #logger.info(f"定时任务启用状态已更新为: {self.enabled}")
        #try:
        #    self.save_schedule()
        #    logger.info("定时任务配置已保存")
        #except Exception as e:
        #    logger.error(f"保存定时任务配置时出错: {e}")
        # 清理临时目录
        #import shutil
        #if os.path.exists(self.temp_dir):
        #    shutil.rmtree(self.temp_dir)
        #    logger.info("临时目录已清理")
        #else:
        #    logger.info("临时目录不存在，无需清理")

    @filter.command("gg_tasks")
    async def toggle(self, event: AstrMessageEvent):
        """
        切换定时任务的启用/禁用状态
        """
        self.enabled = not self.enabled
        status = "启用" if self.enabled else "禁用"
        self.config["enabled"] = self.enabled
        self.save_config()  # 保存配置文件
        self.save_schedule()  # 保存更新后的配置
        yield event.plain_result(f"今日简报定时任务已{status}")        
        self.load_schedule()  # 载入初始化

    @filter.command("cl_time")
    async def reset_time(self, event: AstrMessageEvent):
        '''取消当前群组的定时发送'''
        group_id = self.get_group_id(event.unified_msg_origin)
        if group_id in self.group_schedules:
            del self.group_schedules[group_id]
            self.save_schedule()
            yield event.plain_result("本群组定时发送已取消")
        else:
            yield event.plain_result("本群组未设置发送时间")

    @filter.command("zxs_test")
    async def execute_now(self, event: AstrMessageEvent):
        '''立即发送今日简报！'''
        image_path = await self.get_zxs_image()
        if not image_path:
            yield event.plain_result("获取今日简报失败，请稍后再试")
            return
        # 判断是本地路径还是URL
        if os.path.exists(image_path):
            # 本地文件
            chain = [
                Plain("📰 今日简报"),
                Image.fromFileSystem(image_path)
            ]
        else:
            # URL
            chain = [
                Plain("📰 今日简报"),
                Image.fromURL(image_path)
            ]
        # 发送失败重试
        max_retries = 3
        for retry in range(max_retries):
            try:
                yield event.chain_result(chain)
                logger.info("今日简报发送成功。")
                break
            except Exception as e:
                if retry < max_retries - 1:
                    logger.error(f"发送消息失败，第 {retry + 1} 次重试: {str(e)}")
                    await asyncio.sleep(5)  # 等待 5 秒后重试
                else:
                    logger.error(f"发送消息失败，达到最大重试次数: {str(e)}")
                    yield event.plain_result("发送消息失败，请稍后再试")

    @filter.command("zxs_timezone")
    async def set_timezone(self, event: AstrMessageEvent, timezone: str):
        """
        设置发送今日简报的时区
        如 'Asia/Shanghai'
        """
        try:
            self.user_custom_timezone = ZoneInfo(timezone)
            self.config['default_timezone'] = timezone
            yield event.plain_result(f"时区已设置为: {timezone}")
            self.save_config()  # 添加保存配置的操作
        except ZoneInfoNotFoundError:
            yield event.plain_result("未知的时区，请输入有效的时区名称，例如：Asia/Shanghai")

    @filter.command("zxs_help")
    async def show_help(self, event: AstrMessageEvent):
        """
        显示所有功能帮助信息
        """
        help_text = """📚 走小散每日简报 - 功能帮助

🔹 基础功能：
/zxs_time <时间>       - 设置当前群组定时发送时间（格式：HH:MM 或 HHMM）
                        例如：/zxs_time 08:00 或 /zxs_time 0800
/zxs_test             - 立即测试发送今日简报
/zxs_help             - 显示此帮助信息

🔹 定时任务管理：
/cl_time              - 取消当前群组的定时发送
/gg_tasks             - 切换全局定时任务开关（启用/禁用）
/zxs_doc [序号]        - 查看定时任务列表
                        例如：/zxs_doc 或 /zxs_doc 1,2,3

🔹 配置功能：
/zxs_timezone <时区>   - 设置时区（例如：Asia/Shanghai）

💡 提示：
- 定时任务只在工作日发送（节假日自动跳过）
- 每个群组可以独立设置发送时间
- 默认时区为 Asia/Shanghai"""
        yield event.plain_result(help_text)

    @filter.command("zxs_doc")
    async def list_schedules(self, event: AstrMessageEvent, indices: str = ""):
        """
        列出所有定时任务，支持通过序号查看详情
        例如：/zxs_doc 或 /zxs_doc 1,2,3,4
        """
        # 过滤出有效的定时任务（有时间设置的）
        valid_schedules = []
        for group_id, schedule_info in self.group_schedules.items():
            time_str = schedule_info.get('time')
            target = schedule_info.get('target')
            if time_str:  # 只显示已设置时间的任务
                valid_schedules.append({
                    'group_id': group_id,
                    'time': time_str,
                    'target': target
                })
        
        if not valid_schedules:
            yield event.plain_result("当前没有正在运行的定时任务")
            return
        
        # 如果没有提供序号，显示所有任务列表
        if not indices or indices.strip() == "":
            result_lines = [f"📋 当前共有 {len(valid_schedules)} 个定时任务：\n"]
            for idx, schedule in enumerate(valid_schedules, 1):
                group_id = schedule['group_id']
                time_str = schedule['time']
                # 格式化群组ID显示（如果太长则截断）
                display_id = group_id if len(str(group_id)) <= 30 else str(group_id)[:27] + "..."
                result_lines.append(f"{idx}. 群组: {display_id}")
                result_lines.append(f"   时间: {time_str}")
                
                # 计算下次发送时间
                now = datetime.datetime.now(self.user_custom_timezone)
                next_time = self.get_next_target_time(now, time_str)
                if next_time:
                    result_lines.append(f"   下次发送: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                result_lines.append("")
            
            result_lines.append("💡 使用 /zxs_doc 1,2,3 查看指定序号的详细信息")
            yield event.plain_result("\n".join(result_lines))
            return
        
        # 如果提供了序号，显示指定任务的详细信息
        try:
            # 解析序号（支持逗号分隔的多个序号）
            index_list = [int(idx.strip()) for idx in indices.split(',') if idx.strip().isdigit()]
            
            if not index_list:
                yield event.plain_result("序号格式错误，请输入数字，例如：1 或 1,2,3")
                return
            
            result_lines = ["📋 定时任务详细信息：\n"]
            now = datetime.datetime.now(self.user_custom_timezone)
            
            for index in index_list:
                if index < 1 or index > len(valid_schedules):
                    result_lines.append(f"❌ 序号 {index} 不存在（有效范围：1-{len(valid_schedules)}）\n")
                    continue
                
                schedule = valid_schedules[index - 1]  # 转换为0-based索引
                group_id = schedule['group_id']
                time_str = schedule['time']
                target = schedule['target']
                
                result_lines.append(f"【任务 {index}】")
                result_lines.append(f"群组ID: {group_id}")
                result_lines.append(f"发送时间: {time_str}")
                
                # 计算下次发送时间
                next_time = self.get_next_target_time(now, time_str)
                if next_time:
                    time_until = next_time - now
                    hours = int(time_until.total_seconds() // 3600)
                    minutes = int((time_until.total_seconds() % 3600) // 60)
                    result_lines.append(f"下次发送: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    result_lines.append(f"距离下次发送: {hours}小时{minutes}分钟")
                
                # 显示任务状态
                result_lines.append(f"任务状态: {'✅ 正常' if target else '⚠️ 待激活'}")
                result_lines.append(f"时区: {self.user_custom_timezone}")
                result_lines.append("")
            
            yield event.plain_result("\n".join(result_lines))
            
        except ValueError:
            yield event.plain_result("序号格式错误，请输入数字，例如：1 或 1,2,3")
        except Exception as e:
            logger.error(f"查看定时任务列表时出错: {e}")
            yield event.plain_result(f"查看定时任务列表时出错: {str(e)}")

    def get_next_target_time(self, now, time_str):
        """
        根据当前时间和时间字符串计算下一次发送今日简报的目标时间。
        
        参数:
            now: 当前时间（datetime.datetime 对象）
            time_str: 时间字符串，格式为 'HH:MM'
        
        返回:
            下一次发送今日简报的目标时间（datetime.datetime 对象）
        """
        if not time_str:
            return None
        # 从时间字符串中提取小时和分钟
        target_hour, target_minute = map(int, time_str.split(':'))
        # 创建目标时间对象，将当前时间的小时和分钟替换为目标小时和分钟
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        # 如果当前时间已经超过目标时间，将目标时间设置为明天的同一时间
        if now > target_time:
            target_time = target_time + datetime.timedelta(days=1)
        return target_time

    async def scheduled_task(self):
        if not self.enabled:
            logger.info("定时任务未启用，跳过执行。")
            return
        logger.info("定时任务开始执行，支持多群组独立时间设置")
        # 用于记录每个群组上次执行的时间，避免重复发送
        group_last_executed = {}
        
        while True:
            if not self.enabled:
                await asyncio.sleep(60)
                continue
            try:
                # 获取当前时间，使用用户自定义的时区
                now = datetime.datetime.now(self.user_custom_timezone)
                
                # 检查当前日期是否为工作日
                is_workday = calendar.is_workday(now.date())
                
                if not is_workday:
                    # 如果不是工作日，等待到下一天午夜再检查
                    next_day = now + datetime.timedelta(days=1)
                    next_day_midnight = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
                    time_until_next_day = (next_day_midnight - now).total_seconds()
                    logger.info(f"当前日期 {now.date()} 不是工作日，等待到下一天午夜（{int(time_until_next_day)} 秒）")
                    await asyncio.sleep(min(time_until_next_day, 3600))  # 最多等待1小时
                    continue
                
                # 检查所有群组，看是否有需要发送的
                groups_to_send = []
                for group_id, schedule_info in self.group_schedules.items():
                    time_str = schedule_info.get('time')
                    target = schedule_info.get('target')
                    
                    if not time_str or not target:
                        continue
                    
                    # 解析时间
                    try:
                        target_hour, target_minute = map(int, time_str.split(':'))
                        # 检查当前时间是否匹配目标时间（小时和分钟都匹配）
                        if now.hour == target_hour and now.minute == target_minute:
                            # 检查今天是否已经发送过
                            today_key = f"{group_id}_{now.date()}"
                            last_executed = group_last_executed.get(today_key)
                            
                            # 如果今天还没发送过，则加入发送列表
                            if last_executed is None or last_executed.date() != now.date():
                                groups_to_send.append((group_id, target, time_str))
                                logger.info(f"群组 {group_id} 时间已到 ({time_str})，准备发送")
                    except Exception as e:
                        logger.error(f"处理群组 {group_id} 的时间设置时出错: {e}")
                        continue
                
                # 如果有群组需要发送，则发送消息
                if groups_to_send:
                    logger.info(f"检测到 {len(groups_to_send)} 个群组需要发送今日简报")
                    # 获取今日简报图片（所有群组共用一张图片）
                    image_path = await self.get_zxs_image()
                    
                    if image_path:
                        # 为每个群组发送消息
                        for group_id, target, time_str in groups_to_send:
                            try:
                                # 判断是本地路径还是URL
                                if os.path.exists(image_path):
                                    # 本地文件
                                    message_chain = MessageChain([
                                        Plain("📰 今日简报"),
                                        Image.fromFileSystem(image_path)
                                    ])
                                else:
                                    # URL
                                    message_chain = MessageChain([
                                        Plain("📰 今日简报"),
                                        Image.fromURL(image_path)
                                    ])
                                
                                # 发送失败重试机制
                                max_retries = 3
                                sent = False
                                for retry in range(max_retries):
                                    try:
                                        await self.context.send_message(target, message_chain)
                                        logger.info(f"群组 {group_id} 今日简报发送成功")
                                        # 记录发送时间
                                        today_key = f"{group_id}_{now.date()}"
                                        group_last_executed[today_key] = now
                                        sent = True
                                        break
                                    except Exception as e:
                                        if retry < max_retries - 1:
                                            logger.error(f"群组 {group_id} 发送消息失败，第 {retry + 1} 次重试: {str(e)}")
                                            await asyncio.sleep(2)  # 等待 2 秒后重试
                                        else:
                                            logger.error(f"群组 {group_id} 定时发送消息失败: {str(e)}")
                                
                                if not sent:
                                    logger.error(f"群组 {group_id} 发送失败，已达到最大重试次数")
                            except Exception as e:
                                logger.error(f"为群组 {group_id} 发送消息时出错: {e}")
                    else:
                        logger.error("获取今日简报图片失败，跳过本次发送")
                
                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                # 记录定时任务出错的错误日志
                logger.error(f"定时任务出错: {str(e)}")
                logger.error(f"错误详情: {e.__class__.__name__}")
                import traceback
                logger.error(f"堆栈信息: {traceback.format_exc()}")
                # 出错后等待 60 秒再重试
                await asyncio.sleep(60)
         



