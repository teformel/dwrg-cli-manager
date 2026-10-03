"""
第五人格命令行管理器
"""

__version__ = "1.0.0"
__author__ = "DWRG Team"
__email__ = "team@dwrg.com"

# 延迟导入，避免循环导入
def get_app():
    from .main import app
    return app

__all__ = ["__version__", "__author__", "__email__"]
