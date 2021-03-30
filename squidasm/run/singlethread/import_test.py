import importlib

if __name__ == "__main__":
    spec = importlib.util.spec_from_file_location(
        "mod", "examples/apps/bqc_5_1/app_server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
