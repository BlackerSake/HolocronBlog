# Holocron Blog 开发复盘

> 项目阶段性完结于 2026-09-17,记录从设计到部署的完整过程、踩过的坑和反思.

## 1. 项目概述

- **目标**：一个基于 FastAPI + Vue 3 的内容论坛,支持文章、评论、点赞、通知、分类、标签、后台管理.
- **重点**：不是功能堆叠,而是通过压测定位高并发链路瓶颈,并做针对性优化.
- **时间**：2 个月前 - 2026年6月24日 12:06
- **状态**：核心功能完成,已部署上线;横向功能待后续.

下面将针对bug并以时间顺序进行
>2a62b3d(2026-06-24)→ 7145e3d(2026-09-17,截止当前文档编写),共 67 个提交,跨度近 3 个月
--

## 2.踩坑全记录

### 1. 时区问题: 反复横跳
> 本质上是看看太浅了,每次哪边显示错就改哪边,始终没有定下**db用 UTC、前端用时区**这条准则
#### 第一次: **硬编码东八区**
尝试直接获取当前时间,上海时区
- `app/core/security.py`中`expire = datetime.now(ZoneInfo("Asia/Shanghai")) + expires_delta` 
- `app/models/user.py` 中 `default=lambda: datetime.now(ZoneInfo("Asia/Shanghai"))`
>当时考虑的是本地时间优先嘛,先让功能跑起来

#### 第二次: **砍掉 ZoneInfo 换 UTC**
- 把 `security.py&user.py` 改为 `datetime.now(timezone.utc)`,`from zoneinfo import ZoneInfo` 删除.但只改了这两个文件;
- 后面新建的 Article 继承 UTC，才补上 `DateTime(timezone=True)`;
- `Category&Tag` 仍是 `server_default=func.now()`  
**口径从这时起就不统一了**
>有意识到用UTC标准,但是没改完,后面新增的`Category&Tag`都没做迁移. 局部正确引发的幻觉

#### 第三次: **前端的反复横跳**

- 后端存储为UTC,但是序列化后的ISO字符串不带时区后缀(native),浏览器按照本地时间解析.**直接导致前端显示 与本地时间相差8小时**  
> 想法是直接解决问题,在前端解析时加小补丁: `d += "Z"`. 前端直接止血,先让显示正确
- 随后前端补丁成本反噬,选择了删去补丁,并将时区加入config,统一调配.
- 更改写入db规则: 从db生成`server_default=func.now()` 改为python写入:`defalut=lambda:` 

  
#### 第四次: **定下规矩:db用UTC,展示用时区**
- 将`settings.tz` 改为 `timezone.utc`.
- 新增补丁 把前端时间戳显示改为时区感知以确保显示正确
- 并将 列类型与 历史数据一并迁移,最终统一 utc

### 5s超时 演变为 数据库雪崩
redis-py 升级后,socket_timeout 默认从无限等待变为了5秒. 而 Stream 消费者使用`XREADGROUP BLOCK 5000`  
1. 阻塞读取达到 5s
2. Redis 客户端 抛出TimeoutError
3. 消费者进程退出
4. 缓存预热 和异步写库 停止
5. 请求路径降级 直接查db,导致db压力剧增
6. 触发断融,延迟和错误进一步扩大
>本质就是 一个点的冲突发生了连锁反应,触发降级路径,而降级路径会把压力转移到更脆弱的组件

### Stream 数据语义上的 配置错误
消费组创建时有两个符号`0`和`$`:
- `0`:从已有历史消息开始消费
- `$`:只消费 组创建之后的新消息
在测压的时候,流程是"先生产点赞事件,再启动Worker追平",那么消费者就得用`0` 而不是`$`.否则就会出现历史消息被跳过的情况.

### toggle 没有搞幂等操作,
点赞的最初设计 toggle **每个请求都反转状态并XADD一个事件**:
- 请求一次: 点赞
- 再次请求: 取消点赞
在并发+重试+网络超时的情况下,这套toggle会产生问题:
- **重复点击/重试:** 用户双击/前端重发 都会产生新事件,
- **状态翻转有竞争态:** 最终状态=初始状态XOR请求个数,这导致两个并发"我要点赞"请求,最终可能变为"点赞,然后取消点赞"
- 如果发送15000个请求,则产生15767条待消费记录,虽然worker `_dedupe` 后大部分相互抵消,但落库的吞吐仍会被垃圾流量填满.
==改为幂等状态设置(PUT + is_liked 显示传参) ==
```python
if desired == 1 then changed = redis.call("SADD",KEYS[1],ARGV[1])
else changed = redis.call("SERM",KEYS[1],ARGV[1]) end
local count = redis.call("SADD",KEYS[1])
if changed == 1 then redis.call("XADD",KEYS[2],...) end
return {desired,count,changed}
```
