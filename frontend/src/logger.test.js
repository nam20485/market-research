import { afterEach, describe, expect, it, vi } from 'vitest'
import { logger } from './logger.js'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('logger', () => {
  it('prefixes console methods', () => {
    const info = vi.spyOn(console, 'info').mockImplementation(() => {})
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const error = vi.spyOn(console, 'error').mockImplementation(() => {})
    const debug = vi.spyOn(console, 'debug').mockImplementation(() => {})

    logger.info('a', 1)
    logger.warn('b')
    logger.error('c')
    logger.debug('d')

    expect(info).toHaveBeenCalledWith('[market-research]', 'a', 1)
    expect(warn).toHaveBeenCalledWith('[market-research]', 'b')
    expect(error).toHaveBeenCalledWith('[market-research]', 'c')
    expect(debug).toHaveBeenCalledWith('[market-research]', 'd')
  })
})
