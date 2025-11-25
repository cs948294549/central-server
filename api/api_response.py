from flask import jsonify
from typing import Any, Optional
import time

class APIResponse:
    """
    API统一响应格式类
    用于封装所有API的返回格式，确保接口返回格式的一致性
    """
    
    # 响应状态码
    SUCCESS_CODE = 0
    ERROR_CODE = 1
    PARAM_ERROR_CODE = 400
    AUTH_ERROR_CODE = 401
    FORBIDDEN_ERROR_CODE = 403
    NOT_FOUND_ERROR_CODE = 404
    SERVER_ERROR_CODE = 500
    
    # 响应消息
    SUCCESS_MESSAGE = "success"
    ERROR_MESSAGE = "error"
    PARAM_ERROR_MESSAGE = "参数错误"
    AUTH_ERROR_MESSAGE = "认证失败"
    FORBIDDEN_ERROR_MESSAGE = "权限不足"
    NOT_FOUND_MESSAGE = "资源不存在"
    SERVER_ERROR_MESSAGE = "服务器内部错误"
    
    @classmethod
    def success(cls, data: Any = None, message: str = SUCCESS_MESSAGE, code: int = SUCCESS_CODE) -> Any:
        """
        成功响应
        
        Args:
            data: 返回的数据，可以是任意类型
            message: 响应消息，默认为"success"
            code: 响应码，默认为0
            
        Returns:
            Flask jsonify对象
        """
        response = {
            'code': code,
            'message': message,
            'timestamp': int(time.time() * 1000),  # 毫秒级时间戳
            'data': data
        }
        return jsonify(response)
    
    @classmethod
    def error(cls, message: str = ERROR_MESSAGE, code: int = ERROR_CODE, data: Any = None) -> Any:
        """
        错误响应
        
        Args:
            message: 错误消息，默认为"error"
            code: 错误码，默认为1
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        response = {
            'code': code,
            'message': message,
            'timestamp': int(time.time() * 1000),  # 毫秒级时间戳
            'data': data
        }
        return jsonify(response)
    
    @classmethod
    def param_error(cls, message: str = PARAM_ERROR_MESSAGE, data: Any = None) -> Any:
        """
        参数错误响应
        
        Args:
            message: 错误消息，默认为"参数错误"
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        return cls.error(message=message, code=cls.PARAM_ERROR_CODE, data=data)
    
    @classmethod
    def auth_error(cls, message: str = AUTH_ERROR_MESSAGE, data: Any = None) -> Any:
        """
        认证失败响应
        
        Args:
            message: 错误消息，默认为"认证失败"
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        return cls.error(message=message, code=cls.AUTH_ERROR_CODE, data=data)
    
    @classmethod
    def forbidden_error(cls, message: str = FORBIDDEN_ERROR_MESSAGE, data: Any = None) -> Any:
        """
        权限不足响应
        
        Args:
            message: 错误消息，默认为"权限不足"
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        return cls.error(message=message, code=cls.FORBIDDEN_ERROR_CODE, data=data)
    
    @classmethod
    def not_found_error(cls, message: str = NOT_FOUND_MESSAGE, data: Any = None) -> Any:
        """
        资源不存在响应
        
        Args:
            message: 错误消息，默认为"资源不存在"
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        return cls.error(message=message, code=cls.NOT_FOUND_ERROR_CODE, data=data)
    
    @classmethod
    def server_error(cls, message: str = SERVER_ERROR_MESSAGE, data: Any = None) -> Any:
        """
        服务器内部错误响应
        
        Args:
            message: 错误消息，默认为"服务器内部错误"
            data: 附加数据，默认为None
            
        Returns:
            Flask jsonify对象
        """
        return cls.error(message=message, code=cls.SERVER_ERROR_CODE, data=data)
    
    @classmethod
    def with_status_code(cls, response_data: Any, status_code: int = 200) -> Any:
        """
        为响应添加HTTP状态码
        
        Args:
            response_data: 响应数据
            status_code: HTTP状态码，默认为200
            
        Returns:
            Flask jsonify对象（带状态码）
        """
        return response_data, status_code

# 导出APIResponse类
__all__ = ['APIResponse']