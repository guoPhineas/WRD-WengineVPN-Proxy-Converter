# WRD WengineVPN Proxy Converter

[English](#english) · [简体中文](#简体中文)

Turn a Wangruida Wengine WebVPN gateway into a local HTTP/HTTPS proxy. Requests to selected domains are transparently converted to WebVPN URLs, signed with your authentication cookie, and sent through the gateway; all other traffic remains direct.

> [!WARNING]
> This project performs HTTPS interception through `mitmproxy`. Use it only on devices and WebVPN accounts you own or are authorized to access. Never commit a real authentication cookie or install the generated CA certificate on an untrusted device.

---

## English

### Features

- Proxies both HTTP and HTTPS targets through an HTTP or HTTPS WebVPN gateway.
- Encrypts the target authority with Wengine's AES-CFB URL format.
- Limits WebVPN routing to an explicit domain allowlist, including subdomains.
- Recognizes already-encoded absolute and root-relative WebVPN links without double encryption.
- Restores non-allowlisted encoded links to their original direct URLs.
- Converts WebVPN-formatted redirect targets back to their original URLs.
- Lets gateway asset paths bypass all URL and header rewriting.

### How it works

The target URL scheme becomes the first path segment, while the target authority is encrypted by `wengine_decryptor.py`. The WebVPN gateway's own scheme is independent of the target scheme.

```text
https://github.com/example/repo
        │
        └──> http://vpn.example.edu/https/<encrypted-github.com>/example/repo
             └──────── gateway ────────┘ └──────── target URL ───────────┘
```

Only hosts in `PROXY_DOMAIN_WHITELIST` are rewritten. A rule such as `example.com` also matches `www.example.com`, but not `notexample.com`.

### Requirements

- Python 3.10 or later
- A Wengine WebVPN gateway URL
- A valid WebVPN authentication cookie
- Permission to access the target resources through that gateway

### Quick start

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/guoPhineas/WRD-WengineVPN-Proxy-Converter.git
   cd WRD-WengineVPN-Proxy-Converter
   ```

2. Create a virtual environment and install the dependencies:

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   On Windows, replace `.venv/bin/` with `.venv\Scripts\`.

3. Edit the configuration near the top of `webvpn_proxy.py`:

   ```python
   WEBVPN_URL = "https://vpn.example.edu"
   WEBVPN_COOKIE_NAME = "wengine_vpn_ticketvpn_example_edu"
   WEBVPN_COOKIE_VALUE = "replace-with-your-cookie-value"

   WENGINE_KEY = "wrdvpnisthebest!"
   WENGINE_IV = "wrdvpnisthebest!"

   PROXY_DOMAIN_WHITELIST = {
       "github.com",
       "example.com",
   }

   DIRECT_PATH_PREFIXES = {
       "/wengine-vpn/",
   }
   ```

   `WEBVPN_URL` must include `http://` or `https://`. Change the key and IV only when your deployment uses different values.

4. Start the proxy:

   ```bash
   .venv/bin/python webvpn_proxy.py --host 127.0.0.1 --port 8080
   ```

5. Set your application or operating system HTTP **and** HTTPS proxy to `127.0.0.1:8080`.

6. While using the proxy, open [http://mitm.it](http://mitm.it), install the certificate for your platform, and explicitly trust it. This is required for HTTPS inspection.

7. Test a host that is present in your allowlist:

   ```bash
   curl -x http://127.0.0.1:8080 https://github.com/
   ```

### Configuration reference

| Setting | Purpose |
| --- | --- |
| `WEBVPN_URL` | Base URL of the WebVPN gateway, including its scheme and any base path. |
| `WEBVPN_COOKIE_NAME` | Name of the gateway's authentication cookie. |
| `WEBVPN_COOKIE_VALUE` | Current value of the authentication cookie. Keep it secret. |
| `WENGINE_KEY` | AES key used for Wengine URL conversion; must be 16, 24, or 32 bytes. |
| `WENGINE_IV` | AES initialization vector; must be exactly 16 bytes. |
| `PROXY_DOMAIN_WHITELIST` | Target domains routed through WebVPN. Each entry also matches its subdomains. |
| `DIRECT_PATH_PREFIXES` | Path prefixes that bypass every URL, Cookie, and header modification. |

The command-line options only control the local listener:

```text
--host HOST    Listen address (default: 127.0.0.1)
--port PORT    Listen port (default: 8080)
```

Keep the default loopback host unless other devices must connect. Binding to a LAN address exposes the proxy—and potentially your WebVPN session—to that network.

### Request behavior

| Request | Result |
| --- | --- |
| Allowlisted target | Converted to a WebVPN URL; the configured Cookie is attached. |
| Non-allowlisted target | Sent directly without WebVPN rewriting. |
| WebVPN gateway host | Sent to the gateway without another round of encryption; the configured Cookie is attached. |
| Encoded `/http/...` or `/https/...` path | Routed through WebVPN if its decoded host is allowlisted; otherwise restored and sent directly. |
| Path under `DIRECT_PATH_PREFIXES` | Left completely unchanged. |

XHR, `fetch`, JavaScript, CSS, images, and other resources follow the same request rules. The proxy does not rewrite text inside HTML or JavaScript; Wengine installations normally generate their own encoded resource links.

### URL helper module

`wengine_decryptor.py` contains the AES-CFB conversion helpers used by the proxy:

```python
from wengine_decryptor import decrypt_webvpn_url, encrypt_webvpn_url

key = iv = "wrdvpnisthebest!"
encoded = encrypt_webvpn_url("github.com", key, iv)
decoded = decrypt_webvpn_url(encoded, key, iv)
```

### Troubleshooting

- **HTTPS certificate error:** visit `http://mitm.it` through the running proxy, install the correct certificate, and mark it as trusted.
- **Request is not routed through WebVPN:** confirm that the hostname—or its parent domain—is in `PROXY_DOMAIN_WHITELIST`.
- **Gateway redirects to sign-in:** refresh `WEBVPN_COOKIE_VALUE`; WebVPN session cookies usually expire.
- **Gateway assets fail to load:** make sure its asset directory is listed in `DIRECT_PATH_PREFIXES`.
- **Proxy starts with a configuration error:** verify the gateway URL, Cookie name, AES key length, and IV length.

### Security notes

- The authentication cookie is currently stored as plain text in `webvpn_proxy.py`. Keep your configured copy private.
- A trusted mitmproxy CA can decrypt HTTPS traffic routed through this proxy. Remove it when you no longer need it.
- The proxy replaces the Cookie header only for requests sent to the WebVPN gateway. Direct bypass paths are left unchanged.
- Access to remote systems remains subject to your institution's policies and authorization rules.

### License

Released under the [MIT License](LICENSE).

---

## 简体中文

### 功能简介

本项目将网瑞达 Wengine WebVPN 网关转换为本地 HTTP/HTTPS 代理。访问指定域名时，代理会自动生成 WebVPN 加密 URL、附加认证 Cookie，并通过网关请求资源；其他流量仍然直连。

- 同时支持 HTTP 和 HTTPS 目标网址，WebVPN 网关自身也可使用 HTTP 或 HTTPS。
- 使用 Wengine 的 AES-CFB URL 格式加密目标主机名及端口。
- 仅代理白名单域名，并自动匹配其子域名。
- 识别已加密的绝对链接和根相对链接，避免重复加密。
- 已加密链接的真实域名不在白名单时，会还原为原始 URL 并直连。
- 自动把 WebVPN 格式的重定向地址还原为原始地址。
- 可指定网关静态资源目录，使其完全绕过 URL 和请求头改写。

### 工作原理

目标网址的协议会成为路径的第一段，目标主机名及端口由 `wengine_decryptor.py` 加密。WebVPN 网关使用的协议与目标网址的协议相互独立。

```text
https://github.com/example/repo
        │
        └──> http://vpn.example.edu/https/<加密后的 github.com>/example/repo
             └──────── WebVPN 网关 ────────┘ └──────── 原目标网址 ─────────┘
```

只有 `PROXY_DOMAIN_WHITELIST` 中的主机才会被改写。例如，`example.com` 同时匹配 `www.example.com`，但不会匹配 `notexample.com`。

### 环境要求

- Python 3.10 或更高版本
- Wengine WebVPN 网关地址
- 有效的 WebVPN 登录 Cookie
- 已获授权通过该网关访问目标资源

### 快速开始

1. 克隆仓库并进入项目目录：

   ```bash
   git clone https://github.com/guoPhineas/WRD-WengineVPN-Proxy-Converter.git
   cd WRD-WengineVPN-Proxy-Converter
   ```

2. 创建虚拟环境并安装依赖：

   ```bash
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

   Windows 用户请将 `.venv/bin/` 替换为 `.venv\Scripts\`。

3. 修改 `webvpn_proxy.py` 顶部的配置：

   ```python
   WEBVPN_URL = "https://vpn.example.edu"
   WEBVPN_COOKIE_NAME = "wengine_vpn_ticketvpn_example_edu"
   WEBVPN_COOKIE_VALUE = "replace-with-your-cookie-value"

   WENGINE_KEY = "wrdvpnisthebest!"
   WENGINE_IV = "wrdvpnisthebest!"

   PROXY_DOMAIN_WHITELIST = {
       "github.com",
       "example.com",
   }

   DIRECT_PATH_PREFIXES = {
       "/wengine-vpn/",
   }
   ```

   `WEBVPN_URL` 必须包含 `http://` 或 `https://`。只有在你的 WebVPN 使用不同参数时，才需要修改密钥和 IV。

4. 启动本地代理：

   ```bash
   .venv/bin/python webvpn_proxy.py --host 127.0.0.1 --port 8080
   ```

5. 将应用或操作系统的 HTTP 和 HTTPS 代理都设为 `127.0.0.1:8080`。

6. 通过该代理打开 [http://mitm.it](http://mitm.it)，下载对应平台的证书，安装后明确设为信任。HTTPS 解密必须完成此步骤。

7. 使用已加入白名单的域名测试：

   ```bash
   curl -x http://127.0.0.1:8080 https://github.com/
   ```

### 配置说明

| 配置项 | 作用 |
| --- | --- |
| `WEBVPN_URL` | WebVPN 网关的完整基础地址，包含协议和可选的基础路径。 |
| `WEBVPN_COOKIE_NAME` | 网关认证 Cookie 的名称。 |
| `WEBVPN_COOKIE_VALUE` | 当前认证 Cookie 的值，请妥善保密。 |
| `WENGINE_KEY` | Wengine URL 转换使用的 AES 密钥，长度必须为 16、24 或 32 字节。 |
| `WENGINE_IV` | AES 初始化向量，长度必须为 16 字节。 |
| `PROXY_DOMAIN_WHITELIST` | 需要通过 WebVPN 访问的目标域名，每项同时匹配其子域名。 |
| `DIRECT_PATH_PREFIXES` | 完全跳过 URL、Cookie 和请求头修改的路径前缀。 |

命令行参数只控制本地监听地址：

```text
--host HOST    监听地址，默认为 127.0.0.1
--port PORT    监听端口，默认为 8080
```

除非确实需要让其他设备连接，否则请保留默认的本机回环地址。监听局域网地址会将代理以及潜在的 WebVPN 会话暴露给同一网络中的设备。

### 请求处理规则

| 请求类型 | 处理结果 |
| --- | --- |
| 白名单目标域名 | 转换为 WebVPN URL，并附加配置的认证 Cookie。 |
| 非白名单目标域名 | 不改写，直接访问目标服务器。 |
| WebVPN 网关域名 | 不再次加密，直接访问网关并附加认证 Cookie。 |
| 已加密的 `/http/...` 或 `/https/...` 路径 | 解密后的域名在白名单中则通过网关访问，否则还原并直连。 |
| `DIRECT_PATH_PREFIXES` 下的路径 | URL、Cookie 和请求头均保持不变。 |

XHR、`fetch`、JavaScript、CSS、图片等动态资源都会遵循同一套规则。代理不会改写 HTML 或 JavaScript 文本中的链接；通常 Wengine 会自行生成已加密的资源链接。

### URL 加解密模块

`wengine_decryptor.py` 提供代理内部使用的 AES-CFB 加解密函数：

```python
from wengine_decryptor import decrypt_webvpn_url, encrypt_webvpn_url

key = iv = "wrdvpnisthebest!"
encoded = encrypt_webvpn_url("github.com", key, iv)
decoded = decrypt_webvpn_url(encoded, key, iv)
```

### 常见问题

- **HTTPS 提示证书错误：** 通过正在运行的代理访问 `http://mitm.it`，安装对应证书并将其设为信任。
- **请求没有经过 WebVPN：** 检查目标主机名或其上级域名是否已加入 `PROXY_DOMAIN_WHITELIST`。
- **网关跳转到登录页：** 更新 `WEBVPN_COOKIE_VALUE`，WebVPN 会话 Cookie 通常会过期。
- **网关静态资源加载失败：** 确认其资源目录已加入 `DIRECT_PATH_PREFIXES`。
- **启动时提示配置错误：** 检查网关 URL、Cookie 名称、AES 密钥长度和 IV 长度。

### 安全提示

- 认证 Cookie 目前以明文写在 `webvpn_proxy.py` 中，请勿提交包含真实 Cookie 的配置。
- 受信任的 mitmproxy CA 可以解密经过本代理的 HTTPS 流量，不再使用时应将其移除。
- 代理只会为发往 WebVPN 网关的请求替换 Cookie；直接绕过的路径不会被修改。
- 访问远程系统时，仍须遵守所属机构的政策和授权范围。

### 许可证

本项目采用 [MIT License](LICENSE) 发布。
