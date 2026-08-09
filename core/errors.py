"""统一业务异常。

业务校验失败(参数不合法、文件格式错误等)应抛出 AppError 而非裸 HTTPException,
便于与框架/底层异常区分,并在将来扩展错误码等字段。
"""

from fastapi import HTTPException


class AppError(HTTPException):
    """业务异常：携带 HTTP 状态码与用户可读的错误信息。

    继承自 HTTPException,由 core/main.py 注册的全局异常处理器统一转为
    {"detail": ...} JSON 响应,与现有 HTTPException 行为完全兼容。
    """
