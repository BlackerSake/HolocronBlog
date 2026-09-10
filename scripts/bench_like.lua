-- 用法
-- wrk -t4 -c50 -d35s -s scripts/bench_like.lua http://127.0.0.1:8858
-- MODE=toggle wrk ... 交替点赞/取消点赞

local function get_token()
    local user = os.getenv("BENCH_USER")
    local password = os.getenv("BENCH_PASSWORD")
    assert(user and password, "必须设置 BENCH_USER 和 BENCH_PASSWORD 环境变量")
    local base = "http://127.0.0.1:" .. (os.getenv("BENCH_PORT") or "8858")
    local cmd = string.format(
        "curl -s -X POST %s/api/v1/login -d 'username=%s&password=%s'",base,user,password)
    local handle = io.popen(cmd)
    local body = handle:read("*a")
    handle:close()

    local token = body:match('"access_token"%s*:%s*"([^"]+)"')
    assert(token, "登录失败,响应: " .. body)
    return token
end

local token = get_token()
assert(token, "login error 拿不到token")
    
wrk.method = "PUT"
wrk.headers["Content-Type"] = "application/json"
wrk.headers["Authorization"] = "Bearer " .. token 

local mode = os.getenv("MODE") or "fixed"
local counter = 0

-- wrk 每个请求调用一次 req() 返回http请求
-- 每个wrk线程拥有独立lua状态,counter不跨线程共享: 

function request()
    if mode == "toggle" then
        counter = counter + 1
        if counter % 2 ==0 then
            wrk.body = '{"is_liked":true}'
        else
            wrk.body = '{"is_liked":false}'
        end
    else
        wrk.body = '{"is_liked":true}'
    end
    return wrk.format(nil) --nil = CLI 的URL
end

local statuses = {}

