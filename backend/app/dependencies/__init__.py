from typing import Annotated

from fastapi import Depends
from hf_xet import __all__

from app.common.storage import AvatarFileStorage, KnowledgeFileStorage
from app.modules.users.models import User

from .auth import get_current_user
from .pagination import PageParams, get_page_params
from .storage import get_avatar_storage, get_kb_file_storage

# 当前登录用户依赖项类型
CurrentUser = Annotated[User, Depends(get_current_user)]

# 分页参数依赖项类型
Pagination = Annotated[PageParams, Depends(get_page_params)]

# 头像存储依赖项类型
AvatarStorage = Annotated[AvatarFileStorage, Depends(get_avatar_storage)]

# 知识库文件存储依赖项类型
KBFileStorage = Annotated[KnowledgeFileStorage, Depends(get_kb_file_storage)]
