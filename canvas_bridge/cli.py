import argparse
import json
from pathlib import Path
import sys

from .config import BridgeError
from .service import CanvasService


TOOLS = ("list_courses", "get_course", "list_assignments", "get_assignment", "list_modules",
         "list_module_items", "list_pages", "get_page", "list_announcements", "list_course_materials",
         "download_material", "read_material", "get_upcoming_work", "get_assignment_context")


def main():
    parser = argparse.ArgumentParser(description="个人 Canvas 只读连接器")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("serve", help="启动 MCP stdio 服务")
    commands.add_parser("doctor", help="检查配置并连接 Canvas")
    config_parser = commands.add_parser("config", help="打印不含令牌的 MCP 客户端配置")
    config_parser.add_argument("--client", choices=("codex", "deepseek"), default="codex")
    config_parser.add_argument("--name", default="canvas")
    config_parser.add_argument("--config-path")
    configure_parser = commands.add_parser("configure", help="配置学校地址、时区和已有授权凭据文件路径")
    configure_parser.add_argument("--base-url")
    configure_parser.add_argument("--token-file")
    configure_parser.add_argument("--timezone", default="UTC")
    configure_parser.add_argument("--config-path")
    configure_parser.add_argument("--force", action="store_true")
    register_parser = commands.add_parser("register-codex", help="注册到本机 Codex，不向配置写入令牌")
    register_parser.add_argument("--name", default="canvas")
    register_parser.add_argument("--config-path")
    deepseek_parser = commands.add_parser("export-deepseek", help="导出 DeepSeek Harness Cordis overlay，保留现有 profile")
    deepseek_parser.add_argument("--name", default="canvas")
    deepseek_parser.add_argument("--config-path")
    deepseek_parser.add_argument("--output")
    deepseek_parser.add_argument("--profile", default="web")
    commands.add_parser("self-test", help="离线验证 MCP 启动和工具列表，不访问 Canvas")
    call_parser = commands.add_parser("call", help="调用工具，参数用 JSON 传入")
    call_parser.add_argument("tool", choices=TOOLS)
    call_parser.add_argument("--args", default="{}", help='例如 {"course_id":"123"}')
    args = parser.parse_args()
    if args.command == "serve":
        from .server import main as serve
        serve()
        return
    try:
        if args.command == "config":
            from .deployment import mcp_configuration
            from .deepseek import deepseek_configuration
            factory = deepseek_configuration if args.client == "deepseek" else mcp_configuration
            print(json.dumps(factory(args.name, args.config_path), ensure_ascii=False, indent=2))
            return
        if args.command == "export-deepseek":
            from .deepseek import export_deepseek
            result = export_deepseek(args.name, args.config_path, args.output, args.profile)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        if args.command in ("configure", "register-codex", "self-test"):
            from .deployment import configure, register_codex, self_test
            if args.command == "configure":
                result = configure(args.base_url, args.token_file, args.timezone, args.config_path, args.force)
            elif args.command == "register-codex":
                result = register_codex(args.name, args.config_path)
            else:
                result = self_test()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        service = CanvasService()
        if args.command == "doctor":
            courses = service.list_courses()
            result = {"ok": True, "base_url": service.settings.base_url, "credential_loaded": True,
                      "course_count": courses["count"], "truncated": courses["truncated"],
                      "fetched_at": courses["fetched_at"]}
        else:
            arguments = json.loads(args.args)
            if not isinstance(arguments, dict):
                raise BridgeError("--args 必须是 JSON 对象。")
            try:
                result = getattr(service, args.tool)(**arguments)
            except TypeError:
                raise BridgeError("工具参数不正确，请查看 MCP 工具说明或 README。") from None
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BridgeError as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
    except (ValueError, json.JSONDecodeError):
        print('{"ok": false, "error": "参数必须是有效 JSON。"}', file=sys.stderr)
        raise SystemExit(1)
    except Exception:
        print('{"ok": false, "error": "处理失败，未输出原始响应或凭据。"}', file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
