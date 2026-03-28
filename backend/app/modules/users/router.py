from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from app.common.logger import logger
from app.common.responses import APIResponse
from app.dependencies import CurrentUser
from app.dependencies.services import get_user_service
from app.modules.users.schema import (
    AvatarUpdateResponse,
    UserPwdUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.modules.users.service import UserService

router = APIRouter()


@router.get("/info", response_model=APIResponse[UserResponse])
async def get_info(
    user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """获取用户信息"""
    logger.info("接口 用户登录 :'/info' 被访问")
    return APIResponse(data=service.get_user_info(user), message="获取用户信息成功")


@router.put("/update", response_model=APIResponse[UserResponse])
async def update_user(
    update_data: UserUpdateRequest,
    user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """更新用户信息"""
    logger.info("接口 用户更新 :'/update' 被访问")
    result = await service.update_user(user, update_data)
    return APIResponse(data=result, message="更新用户信息成功")


@router.put("/password", response_model=APIResponse)
async def update_password(
    pwd_data: UserPwdUpdateRequest,
    user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
):
    """
    修改密码
    认证Token -> 校验旧密码 -> 加密新密码 -> 更新数据库
    """
    logger.info("接口 更新密码 :'/password' 被访问")
    await service.change_password(user, pwd_data)
    return APIResponse(message="密码修改成功")


@router.post("/avatar", response_model=APIResponse[AvatarUpdateResponse])
async def upload_avatar(
    user: CurrentUser,
    service: Annotated[UserService, Depends(get_user_service)],
    file: UploadFile = File(...),
):
    """
    上传头像
    - 支持格式: jpeg, jpg, png, gif, webp
    - 最大文件大小: 5MB
    """
    logger.info("接口 上传头像 :'/avatar' 被访问")
    avatar_url = await service.upload_avatar(user, file)
    return APIResponse(
        data=AvatarUpdateResponse(avatar=avatar_url), message="头像上传成功"
    )
