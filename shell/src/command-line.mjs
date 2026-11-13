/**
 * The shell's command-line input policy (T08, plan §4.3 and §5).
 *
 * **The property.** The shell accepts no command-line input at all. On
 * Windows an Electron app's `process.argv` and the `second-instance` event's
 * `argv` are the classic channels by which a file path, a `file://` URL or a
 * custom-protocol URL reaches a window — drag a file onto a shortcut icon and
 * the path arrives here. The plan's baseline is that no `file://` and no
 * custom scheme is ever loaded (§5), and that a second instance focuses the
 * first window and starts no second service (§4.3). Both together mean: every
 * user-supplied argument is *refused and reported*, never interpreted, never
 * loaded, never turned into a page.
 *
 * **Why a pure function.** `main.mjs` cannot be imported by a test (it loads
 * `electron` and starts an app). A policy decided inline there has no witness
 * — and a policy with no witness is a policy a counter-mutation can remove
 * while every test stays green. The decision lives here; `main.mjs` only
 * prints what this function returns.
 */

/**
 * Classify the arguments the main process was launched with.
 *
 * @param argv  `process.argv` as Electron handed it to the main process
 * @param options.executableCount  how many leading entries are the runtime's
 *   own (the executable, and in dev the app path). The caller names the count
 *   so the same function serves both shapes: packaged (`LabCairn.exe`) passes
 *   1, dev (`electron .`) passes 2.
 * @returns {{ refused: string[] }} every user-supplied argument, in order.
 *   The shell loads none of them; the caller reports each one.
 */
export function classifyLaunchArguments(argv, { executableCount }) {
  const userArguments = argv.slice(Number(executableCount))
  return { refused: userArguments.map(String) }
}

/**
 * Classify the arguments a second instance forwarded to the running shell.
 *
 * Windows delivers a second launch's command line here (a path dragged onto
 * the icon, a URL handed to the registered handler, anything). The policy is
 * the same as the first launch's: refuse everything, focus the window, start
 * no second service. The working directory is ignored for the same reason —
 * it is input too, and §4.1's rule is that no path is guessed from where the
 * process happens to have been started.
 *
 * @param argv  the second instance's forwarded argument list
 * @returns {{ refused: string[] }}
 */
export function classifySecondInstanceArguments(argv) {
  return { refused: (argv ?? []).map(String) }
}

/** The one line a refusal prints as — the same shape the navigation guards use. */
export function refusalLine(kind, value) {
  return `refused ${kind} ${value}`
}
