"""提示词模板 Schema。"""

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """提示词模板。

    约定：
    - name 唯一标识模板
    - version 语义版本号
    - system 模板正文（含 {{ variable }} 占位符）
    - variables 列出所有可用变量
    """

    name: str = Field(description="模板名称，如 'tutor'")
    version: str = Field(default="1.0.0", description="语义版本号")
    description: str = Field(default="", description="模板用途描述")
    system: str = Field(
        min_length=1,
        description="系统提示词正文，支持 {{ var }} 变量占位",
    )
    variables: list[str] = Field(default_factory=list, description="可用变量列表")
