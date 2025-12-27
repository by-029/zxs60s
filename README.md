# 走小散每日简报

![](C:\Users\Administrator\Desktop\astrbot_plugin_moyurenpro-master\zxs.png)



# 支持

支持自定义时间、时区，自定义api，支持立即发送，工作日定时发送。

需安装第三方库[chinese_calendar](https://github.com/LKI/chinese-calendar)，已配置requirements.txt文件自动安装，异常可手动安装
```
docker exec -it astrbot /bin/bash #docker部署进入astrbot容器，运行bash进行安装

pip install chinesecalendar
```

基础功能
/zxs_time <时间> - 设置当前群组定时发送时间
格式：HH:MM 或 HHMM
示例：/zxs_time 08:00 或 /zxs_time 0800
/zxs_test - 立即测试发送今日简报
/zxs_help - 显示所有功能帮助信息（新功能）
定时任务管理
/cl_time - 取消当前群组的定时发送
/gg_tasks - 切换全局定时任务开关（启用/禁用）
/zxs_doc [序号] - 查看定时任务列表（新功能）
不带参数：显示所有定时任务简要列表
带序号：显示指定序号的详细信息
示例：/zxs_doc 或 /zxs_doc 1,2,3
配置功能
/zxs_timezone <时区> - 设置时区
示例：/zxs_timezone Asia/Shanghai

## 注意事项

- 确保网络连接正常
- 插件依赖外部新闻源，如遇内容获取失败请稍后重试
- 内容更新频率为每日一次

## 版本信息

- 当前版本：v5.3.7
- 作者：走小散
- 更新日期：2025年12月
- 微信扫码关注我
- ![](https://know.zousanzy.cn/qrcode_for_gh_a33c41fcc915_258.jpg)

## 技术支持

如遇使用问题，请通过走小散微信公众号联系作者获取帮助。



![](https://know.zousanzy.cn/2.png)
