"""
MCP exceptions.

错误层级：
MCPError
├── MCPConnectionError    # 连接失败
├── MCPProtocolError      # 协议错误
├── MCPToolExecutionError # 工具执行失败
└── MCPValidationError    # 参数校验失败
"""


class MCPError(Exception):
    """MCP 基础异常。"""

    pass


class MCPConnectionError(MCPError):
    """连接失败（超时、拒绝等）。"""

    pass


class MCPProtocolError(MCPError):
    """协议错误（握手失败、不支持的方法等）。"""

    pass


class MCPToolExecutionError(MCPError):
    """工具执行失败（执行异常、超时等）。"""

    pass


class MCPValidationError(MCPError):
    """参数校验失败（传输类型错误、缺少必要参数等）。"""

    pass
