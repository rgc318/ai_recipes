import os
import sys

# 配置：项目路径和模块路径
REPO_DIR = "app/repositories"
FACTORY_FILE = os.path.join(REPO_DIR, "repository_factory_manul.py")


def snake_case(name: str) -> str:
    # 简单驼峰转蛇形，兼容大部分情况
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def generate_repository_class(entity_name: str) -> str:
    repo_class_name = f"{entity_name}Repository"
    model_name = entity_name
    create_schema = f"{entity_name}Create"
    update_schema = f"{entity_name}Update"

    code = f'''from typing import Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.models.{snake_case(entity_name)} import {model_name}
from app.schemas.{snake_case(entity_name)}_schemas import {create_schema}, {update_schema}
from app.crud.base_repo import BaseRepository


class {repo_class_name}(BaseRepository[{model_name}, {create_schema}, {update_schema}]):
    def __init__(self, db: AsyncSession, context: dict):
        super().__init__({model_name})
        self.db = db
        self.context = context

    # TODO: 自定义你的业务方法
'''
    return code


def add_repo_to_factory(entity_name: str):
    repo_attr_name = entity_name.lower()
    repo_class_name = f"{entity_name}Repository"

    # 读文件
    with open(FACTORY_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 查找是否已存在属性定义
    for line in lines:
        if f"def {repo_attr_name}(self)" in line:
            print(f"[WARN] Factory already has property '{repo_attr_name}'")
            return

    # 寻找class RepositoryFactory:位置，插入属性代码
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if line.strip().startswith("class RepositoryFactory:") and not inserted:
            # 找到类定义后，跳过空行插入
            new_lines.append("\n")
            new_lines.append(f"    @cached_property\n")
            new_lines.append(f"    def {repo_attr_name}(self) -> {repo_class_name}:\n")
            new_lines.append(f"        repo = {repo_class_name}(self._db, context=self.context)\n")
            new_lines.append(f"        self._registry[\"{repo_attr_name}\"] = repo\n")
            new_lines.append(f"        return repo\n\n")
            inserted = True

    # 写回文件
    with open(FACTORY_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"[INFO] Added '{repo_attr_name}' property to RepositoryFactory.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python gen_repo.py EntityName")
        return

    entity_name = sys.argv[1]
    repo_file_path = os.path.join(REPO_DIR, f"{snake_case(entity_name)}_repository.py")

    if os.path.exists(repo_file_path):
        print(f"[ERROR] Repository file '{repo_file_path}' already exists!")
        return

    # 生成 Repository 文件
    repo_code = generate_repository_class(entity_name)
    with open(repo_file_path, "w", encoding="utf-8") as f:
        f.write(repo_code)

    print(f"[INFO] Generated repository file: {repo_file_path}")

    # 向 Factory 添加属性
    add_repo_to_factory(entity_name)


if __name__ == "__main__":
    main()
