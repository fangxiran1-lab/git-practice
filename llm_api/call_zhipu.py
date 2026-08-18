# -*- coding: utf-8 -*-
"""用 requests 调用智谱 GLM（OpenAI 兼容接口）

前置：在 https://open.bigmodel.cn/ 获取 API Key，
把它填到下面的 API_KEY 里（或设置环境变量 ZHIPU_API_KEY）。
"""
import os
import requests

# 0. 若存在 .env 文件，读取里面的 ZHIPU_API_KEY（不装 python-dotenv 的轻量做法）
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
if os.path.exists(_env_path):
    with open(_env_path, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line.startswith("ZHIPU_API_KEY="):
                os.environ.setdefault("ZHIPU_API_KEY", _line.split("=", 1)[1])

# 1. 从环境变量读 Key
API_KEY = os.environ.get("ZHIPU_API_KEY", "")

# 智谱 GLM 的 OpenAI 兼容接口地址（不用改）
URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def chat(prompt, model="glm-4-flash"):
    """发送一轮对话，返回模型回答的文字。

    参数：
        prompt：用户说的话
        model ：模型名（glm-4-flash 免费，glm-4-plus 更聪明）
    """
    if not API_KEY:
        raise ValueError("尚未配置 API Key：请在 .env 里填入 ZHIPU_API_KEY，或设置环境变量 ZHIPU_API_KEY")

    # 2. 构造请求：头部放 Key，正文放消息
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        # 关闭思考模式，加快响应（扫雷这种任务不需要深度推理）
        "thinking": {"type": "disabled"},
        # 限制输出长度：只让它输出坐标，防止长篇大论拖慢响应
        "max_tokens": 50,
        "messages": [
            # role 只有两种常用值：system=设定人设，user=用户说的话
            {"role": "system", "content": "你是一个乐于助人的助手。"},
            {"role": "user", "content": prompt},
        ],
    }

    # 3. 发 POST 请求（类比 C：URL 是地址，headers 是信封上的信息，json=payload 是信件内容）
    resp = requests.post(URL, headers=headers, json=payload, timeout=90)

    # 4. 检查状态码：200 才是成功
    if resp.status_code != 200:
        raise RuntimeError(f"API 返回错误码 {resp.status_code}：{resp.text}")

    # 5. 解析返回的 JSON，一层层取出回答文字
    data = resp.json()                 # 把返回的文本解析成字典
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    if not API_KEY:
        print("请先在 .env 里填入 ZHIPU_API_KEY，或设置环境变量 ZHIPU_API_KEY")
    else:
        answer = chat("用一句话介绍你自己")
        if answer:
            print("模型的回答：")
            print(answer)