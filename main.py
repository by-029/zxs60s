from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import *
import json
import asyncio
import datetime
import aiohttp
import os
import tempfile
from zoneinfo import ZoneInfo
import chinese_calendar as calendar

@register("zxs60s", "egg", "今日简报插件，支持定时发送", "2.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.enabled = config.get("enabled", True)
        self.temp_dir = tempfile.mkdtemp()
        self.config = config
        self.zxs_api_url = "https://know.zousanzy.cn/60/"
        self.user_custom_timezone = ZoneInfo('Asia/Shanghai')
        self.group_schedules = {}
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.schedule_file = os.path.join(plugin_dir, 'schedule.json')
        self.load_schedule()
        asyncio.get_event_loop().create_task(self.scheduled_task()) 
        
    def get_group_id(self, message_target):
        """将消息目标转换为可序列化的群组标识"""
        try:
            return str(message_target)
        except:
            return str(message_target)
    
    def load_schedule(self):
        if not self.enabled:
            return
        if os.path.exists(self.schedule_file):
            try:
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if 'group_schedules' in data:
                        schedules = data.get('group_schedules', {})
                        self.group_schedules = {}
                        for group_id, schedule_info in schedules.items():
                            self.group_schedules[group_id] = {
                                'time': schedule_info.get('time'),
                                'target': None
                            }
                    else:
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
            except Exception as e:
                logger.error(f"加载定时任务信息失败: {e}")
                import traceback
                logger.error(f"错误详情: {traceback.format_exc()}")

    def save_schedule(self):
        schedules_to_save = {}
        for group_id, schedule_info in self.group_schedules.items():
            schedules_to_save[group_id] = {
                'time': schedule_info.get('time')
            }
        data = {'group_schedules': schedules_to_save}
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
        """获取今日简报图片URL或本地路径"""
        try:
            async with aiohttp.ClientSession() as session:
                image_url = await self.get_zxs_image_url(session)
                if image_url:
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
                        return image_url
                return None
        except Exception as e:
            logger.error(f"获取今日简报图片时出错: {e.__class__.__name__}: {str(e)}")
            return None

    def parse_time(self, time: str):
        try:
            hour, minute = map(int, time.split(':'))
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                return None
            return f"{hour:02d}:{minute:02d}"
        except ValueError:
            try:
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
        """设置发送今日简报的时间 格式为 HH:MM或HHMM"""
        time = time.strip()
        parsed_time = self.parse_time(time)
        if not parsed_time:
            yield event.plain_result("时间格式错误，请输入正确的格式，例如：09:00或0900")
            return
        
        group_id = self.get_group_id(event.unified_msg_origin)
        if group_id not in self.group_schedules:
            self.group_schedules[group_id] = {}
        
        self.group_schedules[group_id]['time'] = parsed_time
        self.group_schedules[group_id]['target'] = event.unified_msg_origin
        
        yield event.plain_result(f"本群组今日简报发送时间已设置为: {parsed_time}")
        self.save_schedule()

    def save_config(self):
        """保存配置信息到配置文件"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_dir)
            grandparent_dir = os.path.dirname(os.path.dirname(current_dir))
            config_dir = os.path.join(grandparent_dir, 'config')
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
            config_file = os.path.join(config_dir, 'astrbot_plugin_moyurenpro_config.json')
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"保存配置文件时出错: {e}")

    async def terminate(self):
        """关闭定时任务并清理缓存"""
        pass

    @filter.command("gg_tasks")
    async def toggle(self, event: AstrMessageEvent):
        """切换定时任务的启用/禁用状态"""
        self.enabled = not self.enabled
        status = "启用" if self.enabled else "禁用"
        self.config["enabled"] = self.enabled
        self.save_config()
        self.save_schedule()
        yield event.plain_result(f"今日简报定时任务已{status}")
        self.load_schedule()

    @filter.command("cl_time")
    async def reset_time(self, event: AstrMessageEvent):
        """取消当前群组的定时发送"""
        group_id = self.get_group_id(event.unified_msg_origin)
        if group_id in self.group_schedules:
            del self.group_schedules[group_id]
            self.save_schedule()
            yield event.plain_result("本群组定时发送已取消")
        else:
            yield event.plain_result("本群组未设置发送时间")

    @filter.command("zxs_test")
    async def execute_now(self, event: AstrMessageEvent):
        """立即发送今日简报"""
        image_path = await self.get_zxs_image()
        if not image_path:
            yield event.plain_result("获取今日简报失败，请稍后再试")
            return
        
        if os.path.exists(image_path):
            chain = [
                Image.fromFileSystem(image_path)
            ]
        else:
            chain = [
                Image.fromURL(image_path)
            ]
        
        max_retries = 3
        for retry in range(max_retries):
            try:
                yield event.chain_result(chain)
                logger.info("今日简报发送成功")
                break
            except Exception as e:
                if retry < max_retries - 1:
                    logger.error(f"发送消息失败，第 {retry + 1} 次重试: {str(e)}")
                    await asyncio.sleep(5)
                else:
                    logger.error(f"发送消息失败，达到最大重试次数: {str(e)}")
                    yield event.plain_result("发送消息失败，请稍后再试")

    def get_next_send_time(self, time_str):
        """计算下次发送时间"""
        if not time_str:
            return None
        now = datetime.datetime.now(self.user_custom_timezone)
        try:
            target_hour, target_minute = map(int, time_str.split(':'))
            target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
            if now > target_time:
                target_time = target_time + datetime.timedelta(days=1)
            while not calendar.is_workday(target_time.date()):
                target_time = target_time + datetime.timedelta(days=1)
            return target_time
        except:
            return None

    @filter.command("zxs_doc")
    async def list_tasks(self, event: AstrMessageEvent):
        """列出所有定时任务"""
        active_tasks = []
        inactive_tasks = []
        
        for group_id, schedule_info in self.group_schedules.items():
            time_str = schedule_info.get('time')
            target = schedule_info.get('target')
            
            if time_str:
                next_send_time = self.get_next_send_time(time_str)
                task_info = {
                    'group_id': group_id,
                    'time': time_str,
                    'next_send': next_send_time
                }
                
                if target:
                    active_tasks.append(task_info)
                else:
                    inactive_tasks.append(task_info)
        
        result_lines = []
        
        if active_tasks:
            result_lines.append(f"当前共有{len(active_tasks)}个正在运行的定时任务:")
            for idx, task in enumerate(active_tasks, 1):
                next_send_str = task['next_send'].strftime("%Y-%m-%d %H:%M:%S") if task['next_send'] else "未知"
                result_lines.append(f"{idx}. 群组:{task['group_id']}")
                result_lines.append(f"   时间: {task['time']}")
                result_lines.append(f"   下次发送:{next_send_str}")
        
        if inactive_tasks:
            if result_lines:
                result_lines.append("")
            result_lines.append(f"⚠️ 发现 {len(inactive_tasks)} 个无效的定时任务 (已保存但未激活,不会发送):")
            for idx, task in enumerate(inactive_tasks, len(active_tasks) + 1):
                result_lines.append(f"{idx}. {task['group_id']} - {task['time']}")
            result_lines.append("💡 可以在对应群组使用 /cl_time 清除这些无效任务")
            result_lines.append("💡 或使用 /zxs_up <序号> 激活这些任务")
        
        if not active_tasks and not inactive_tasks:
            result_lines.append("当前没有定时任务")
        
        yield event.plain_result("\n".join(result_lines))

    @filter.command("zxs_doc_del")
    async def delete_task(self, event: AstrMessageEvent, index: str):
        """删除指定序号的定时任务"""
        try:
            task_index = int(index.strip())
        except ValueError:
            yield event.plain_result("序号格式错误，请输入数字")
            return
        
        active_tasks = []
        inactive_tasks = []
        
        for group_id, schedule_info in self.group_schedules.items():
            time_str = schedule_info.get('time')
            target = schedule_info.get('target')
            
            if time_str:
                next_send_time = self.get_next_send_time(time_str)
                task_info = {
                    'group_id': group_id,
                    'time': time_str,
                    'next_send': next_send_time
                }
                
                if target:
                    active_tasks.append(task_info)
                else:
                    inactive_tasks.append(task_info)
        
        all_tasks = active_tasks + inactive_tasks
        
        if task_index < 1 or task_index > len(all_tasks):
            yield event.plain_result(f"序号 {task_index} 无效，当前共有 {len(all_tasks)} 个任务")
            return
        
        task_to_delete = all_tasks[task_index - 1]
        group_id_to_delete = task_to_delete['group_id']
        
        if group_id_to_delete in self.group_schedules:
            del self.group_schedules[group_id_to_delete]
            self.save_schedule()
            yield event.plain_result(f"已删除序号 {task_index} 的定时任务: {group_id_to_delete}")
        else:
            yield event.plain_result(f"删除失败，任务不存在")

    @filter.command("zxs_up")
    async def activate_task(self, event: AstrMessageEvent, index: str):
        """激活指定序号的未激活定时任务"""
        try:
            task_index = int(index.strip())
        except ValueError:
            yield event.plain_result("序号格式错误，请输入数字")
            return
        
        active_tasks = []
        inactive_tasks = []
        inactive_group_ids = []
        
        for group_id, schedule_info in self.group_schedules.items():
            time_str = schedule_info.get('time')
            target = schedule_info.get('target')
            
            if time_str:
                next_send_time = self.get_next_send_time(time_str)
                task_info = {
                    'group_id': group_id,
                    'time': time_str,
                    'next_send': next_send_time
                }
                
                if target:
                    active_tasks.append(task_info)
                else:
                    inactive_tasks.append(task_info)
                    inactive_group_ids.append(group_id)
        
        if not inactive_tasks:
            yield event.plain_result("当前没有未激活的定时任务")
            return
        
        if task_index < len(active_tasks) + 1 or task_index > len(active_tasks) + len(inactive_tasks):
            yield event.plain_result(f"序号 {task_index} 无效，请选择未激活任务的序号 ({len(active_tasks) + 1} - {len(active_tasks) + len(inactive_tasks)})")
            return
        
        inactive_index = task_index - len(active_tasks) - 1
        group_id_to_activate = inactive_group_ids[inactive_index]
        
        if group_id_to_activate in self.group_schedules:
            current_group_id = self.get_group_id(event.unified_msg_origin)
            time_str = self.group_schedules[group_id_to_activate]['time']
            
            if group_id_to_activate != current_group_id:
                self.group_schedules[current_group_id] = {
                    'time': time_str,
                    'target': event.unified_msg_origin
                }
                del self.group_schedules[group_id_to_activate]
            else:
                self.group_schedules[group_id_to_activate]['target'] = event.unified_msg_origin
            
            self.save_schedule()
            yield event.plain_result(f"已激活序号 {task_index} 的定时任务: {time_str}")
        else:
            yield event.plain_result(f"激活失败，任务不存在")


    async def scheduled_task(self):
        if not self.enabled:
            return
        logger.info("定时任务开始执行，支持多群组独立时间设置")
        group_last_executed = {}
        
        while True:
            if not self.enabled:
                await asyncio.sleep(60)
                continue
            try:
                now = datetime.datetime.now(self.user_custom_timezone)
                is_workday = calendar.is_workday(now.date())
                
                if not is_workday:
                    next_day = now + datetime.timedelta(days=1)
                    next_day_midnight = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
                    time_until_next_day = (next_day_midnight - now).total_seconds()
                    logger.info(f"当前日期 {now.date()} 不是工作日，等待到下一天午夜（{int(time_until_next_day)} 秒）")
                    await asyncio.sleep(min(time_until_next_day, 3600))
                    continue
                
                groups_to_send = []
                for group_id, schedule_info in self.group_schedules.items():
                    time_str = schedule_info.get('time')
                    target = schedule_info.get('target')
                    
                    if not time_str or not target:
                        continue
                    
                    try:
                        target_hour, target_minute = map(int, time_str.split(':'))
                        if now.hour == target_hour and now.minute == target_minute:
                            today_key = f"{group_id}_{now.date()}"
                            last_executed = group_last_executed.get(today_key)
                            
                            if last_executed is None or last_executed.date() != now.date():
                                groups_to_send.append((group_id, target, time_str))
                                logger.info(f"群组 {group_id} 时间已到 ({time_str})，准备发送")
                    except Exception as e:
                        logger.error(f"处理群组 {group_id} 的时间设置时出错: {e}")
                        continue
                
                if groups_to_send:
                    logger.info(f"检测到 {len(groups_to_send)} 个群组需要发送今日简报")
                    image_path = await self.get_zxs_image()
                    
                    if image_path:
                        for group_id, target, time_str in groups_to_send:
                            try:
                                if os.path.exists(image_path):
                                    message_chain = MessageChain([
                                        Image.fromFileSystem(image_path)
                                    ])
                                else:
                                    message_chain = MessageChain([
                                        Image.fromURL(image_path)
                                    ])
                                
                                max_retries = 3
                                sent = False
                                for retry in range(max_retries):
                                    try:
                                        await self.context.send_message(target, message_chain)
                                        logger.info(f"群组 {group_id} 今日简报发送成功")
                                        today_key = f"{group_id}_{now.date()}"
                                        group_last_executed[today_key] = now
                                        sent = True
                                        break
                                    except Exception as e:
                                        if retry < max_retries - 1:
                                            logger.error(f"群组 {group_id} 发送消息失败，第 {retry + 1} 次重试: {str(e)}")
                                            await asyncio.sleep(2)
                                        else:
                                            logger.error(f"群组 {group_id} 定时发送消息失败: {str(e)}")
                                
                                if not sent:
                                    logger.error(f"群组 {group_id} 发送失败，已达到最大重试次数")
                            except Exception as e:
                                logger.error(f"为群组 {group_id} 发送消息时出错: {e}")
                    else:
                        logger.error("获取今日简报图片失败，跳过本次发送")
                
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"定时任务出错: {str(e)}")
                logger.error(f"错误详情: {e.__class__.__name__}")
                import traceback
                logger.error(f"堆栈信息: {traceback.format_exc()}")
                await asyncio.sleep(60)
         



