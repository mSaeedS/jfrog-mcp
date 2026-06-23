#!/usr/bin/env node

const { spawn } = require("node:child_process");
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

function exists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

function firstExisting(paths) {
  return paths.find((candidate) => candidate && exists(candidate));
}

function runQuietly(command, args, options) {
  const result = spawnSync(command, args, {
    ...options,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (result.stdout) {
    process.stderr.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}`);
  }
}

function cacheRoot() {
  if (process.env.JFROG_MCP_CACHE_DIR) {
    return path.resolve(process.env.JFROG_MCP_CACHE_DIR);
  }
  if (process.platform === "win32") {
    return path.join(process.env.LOCALAPPDATA || os.tmpdir(), "jfrog-mcp");
  }
  return path.join(process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache"), "jfrog-mcp");
}

function venvPython(venvDir) {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function ensureBootstrapVenv(basePython, packageRoot, version) {
  const venvDir = path.join(cacheRoot(), `venv-${version}`);
  const python = venvPython(venvDir);
  if (exists(python)) {
    return python;
  }

  fs.mkdirSync(path.dirname(venvDir), { recursive: true });
  process.stderr.write(`Bootstrapping jfrog-mcp Python environment in ${venvDir}\n`);
  runQuietly(basePython, ["-m", "venv", venvDir], { cwd: packageRoot });
  runQuietly(python, ["-m", "pip", "install", packageRoot], { cwd: packageRoot });
  return python;
}

const packageRoot = path.resolve(__dirname, "..");
const packageJson = require(path.join(packageRoot, "package.json"));
const projectRoot = process.env.JFROG_MCP_PROJECT_DIR
  ? path.resolve(process.env.JFROG_MCP_PROJECT_DIR)
  : packageRoot;

if (process.argv.includes("--version")) {
  process.stdout.write(`${packageJson.version}\n`);
  process.exit(0);
}

const env = { ...process.env };
const envFile = path.join(projectRoot, ".env");
if (!env.JFROG_ENV_FILE && exists(envFile)) {
  env.JFROG_ENV_FILE = envFile;
}

env.PYTHONPATH = env.PYTHONPATH
  ? `${projectRoot}${path.delimiter}${env.PYTHONPATH}`
  : projectRoot;

const pythonCandidates =
  process.platform === "win32"
    ? [
        env.JFROG_MCP_PYTHON,
        path.join(projectRoot, ".venv", "Scripts", "python.exe"),
        "python",
      ]
    : [
        env.JFROG_MCP_PYTHON,
        path.join(projectRoot, ".venv", "bin", "python3"),
        path.join(projectRoot, ".venv", "bin", "python"),
        "python3",
        "python",
      ];

const basePython = firstExisting(pythonCandidates) || pythonCandidates.at(-1);
const python =
  process.env.JFROG_MCP_SKIP_BOOTSTRAP === "true" ||
  exists(path.join(projectRoot, ".venv"))
    ? basePython
    : ensureBootstrapVenv(basePython, packageRoot, packageJson.version);
const child = spawn(python, ["-m", "jfrog_mcp"], {
  cwd: projectRoot,
  env,
  stdio: "inherit",
  windowsHide: true,
});

child.on("error", (error) => {
  process.stderr.write(`Failed to start jfrog-mcp Python server: ${error.message}\n`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
