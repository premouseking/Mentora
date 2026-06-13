export function pnpmInvocation(
  args,
  {
    platform = process.platform,
    comSpec = process.env.ComSpec,
  } = {},
) {
  if (platform === "win32") {
    if (!comSpec) throw new Error("ComSpec is required on Windows");
    return {
      command: comSpec,
      args: ["/d", "/s", "/c", ["pnpm", ...args].join(" ")],
    };
  }

  return {
    command: "pnpm",
    args,
  };
}
