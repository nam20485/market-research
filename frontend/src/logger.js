// Thin console logger for frontend diagnostics. Keeps a consistent prefix so
// browser filters can isolate app output.

const PREFIX = '[market-research]'

export const logger = {
  info: (...args) => console.info(PREFIX, ...args),
  warn: (...args) => console.warn(PREFIX, ...args),
  error: (...args) => console.error(PREFIX, ...args),
  debug: (...args) => console.debug(PREFIX, ...args),
}
