import importlib.util
import os
import sys
from unittest.mock import MagicMock

# Mock templateframework so plugin scripts that `import templateframework.metadata`
# run without an external runtime installed.
mock_tf = MagicMock()
sys.modules["templateframework"] = mock_tf
sys.modules["templateframework.metadata"] = mock_tf


class MetadataMock:
    def __init__(self):
        self.inputs = {}
        self.computed_inputs = {}
        self.global_inputs = {}


mock_tf.Metadata = MetadataMock


def main():
    if len(sys.argv) < 2:
        print("Usage: script_runner.py <script_path>")
        sys.exit(1)

    script_path = sys.argv[1]
    script_name = os.path.basename(script_path).replace(".py", "")

    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        if not (spec and spec.loader):
            print(f"Error: could not load spec for {script_path}")
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules[script_name] = module
        spec.loader.exec_module(module)

        if not hasattr(module, "run"):
            print(f"Warning: function 'run' not found in {script_name}. Script imported only.")
            return

        print(f"Executing 'run' from {script_name}...")
        try:
            module.run(MetadataMock())
        except TypeError:
            module.run()

    except Exception as error:
        print(f"Error executing script {script_path}: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
