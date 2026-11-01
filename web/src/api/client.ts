/**
 * The one place the workbench talks to the local API.
 *
 * Three things live here and nowhere else, because each of them is a rule
 * rather than a convenience.
 *
 * **Only relative paths.** A path that names a host is refused before a
 * request is made. The workbench is local-first, and the report renders
 * retrieved text: a remote script would be a remote script with the user's
 * material in it. Rather than trusting every call site to pass a path, the
 * boundary refuses anything that is not one — including the two spellings a
 * reader would not think of, ``//host`` and ``\\host``.
 *
 * **The token is a header and nothing else.** A request that changes
 * something carries ``Authorization: Bearer <token>``; a read carries none,
 * because the service asks for the token only on a change. The token never
 * reaches a URL, and it never leaves this module except as that header.
 *
 * **The session response never reaches a caller.** ``GET /session`` is the
 * one response that carries the token, so reading it is not a public method:
 * :meth:`LabCairnClient.sessionPath` asks for it, keeps the token in the
 * module-level holder and returns the *path* of the file the service wrote
 * it to. A caller that asked for the session itself would have the token in
 * a React state, and React state is readable from the outside.
 */

import { API_BASE, apiUrl } from './base'
import type { RefusalBody, SessionInfo } from './generated'
import { API_PATHS } from './paths'
import { forgetSessionToken, holdSessionToken, sessionToken } from './session'

/**
 * A refusal from the service: it understood the request and declined.
 *
 * The two fields are the service's own — the same body every refusal in the
 * API carries — so a caller branches on the reason and reads the message.
 */
export class ApiRefusal extends Error {
  /** The machine-readable reason the service gave. */
  readonly reason: string

  constructor(body: RefusalBody) {
    super(body.message)
    this.name = 'ApiRefusal'
    this.reason = body.reason
  }
}

/**
 * A request that failed for a reason that is not a refusal: the service was
 * not there, or answered with something this client does not understand.
 *
 * **The body is kept, because a caller may have to show it.** A refusal
 * arrives in the refusal body's own shape, but a schema's answer does not:
 * the service answers `422` with the schema's vocabulary, and a panel that
 * could only say "422" would be saying less than the service said. The
 * payload is what the service answered, held verbatim.
 */
export class ApiFailure extends Error {
  /** The status the service answered with, or zero when there was no answer. */
  readonly status: number
  /** What the service answered, when it was not a refusal. */
  readonly payload: unknown

  constructor(status: number, message: string, payload: unknown = null) {
    super(message)
    this.name = 'ApiFailure'
    this.status = status
    this.payload = payload
  }
}

/**
 * A request for something that is not on this origin.
 *
 * Raised before anything is sent, so the refusal costs nothing and leaves no
 * trace in the service's log.
 */
export class ApiPathRefused extends Error {
  constructor(path: string) {
    super(
      `the workbench only asks for paths on its own origin, and ${JSON.stringify(path)} ` +
        'names something else. A local-first tool that phones home is not local-first, ' +
        'and the report renders retrieved text.',
    )
    this.name = 'ApiPathRefused'
  }
}

/**
 * A failure, as the workbench shows it.
 *
 * Two plain fields, so that two failures can be compared — which is what the
 * workbench does to decide whether anything it shows has changed.
 */
export interface ApiError {
  /** The machine-readable reason, when the service refused the request. */
  readonly reason: string | null
  /** The message a person can read. */
  readonly message: string
}

/** The failure an error carries, in the two fields the workbench shows. */
export function describeError(error: unknown): ApiError {
  if (error instanceof ApiRefusal) {
    return { reason: error.reason, message: error.message }
  }
  if (error instanceof ApiFailure) {
    return { reason: null, message: error.message }
  }
  if (error instanceof Error) {
    return { reason: null, message: error.message }
  }
  return { reason: null, message: String(error) }
}

/**
 * Refuse a path that is not a path.
 *
 * Three spellings are refused, and the third is the one that is easy to
 * forget: a browser treats a backslash as a slash in a URL, so
 * ``\\example.com`` addresses a host just as ``//example.com`` does.
 */
export function assertRelativePath(path: string): void {
  if (path.startsWith('//') || path.startsWith('\\\\') || /^[a-z][a-z0-9+.-]*:/i.test(path)) {
    throw new ApiPathRefused(path)
  }
}

/** Whether a payload is the refusal body the service sends. */
function isRefusalBody(payload: unknown): payload is RefusalBody {
  if (typeof payload !== 'object' || payload === null) {
    return false
  }
  const candidate = payload as { reason?: unknown; message?: unknown }
  return typeof candidate.reason === 'string' && typeof candidate.message === 'string'
}

/** A response's JSON, or null when it carries none. */
async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (text === '') {
    return null
  }
  const parsed: unknown = JSON.parse(text)
  return parsed
}

/**
 * The client the workbench reads through.
 *
 * One instance is enough: the service is the only thing this page talks to,
 * and the base it uses is the one the bundle was built for.
 */
export class LabCairnClient {
  /** The path the API is mounted under. */
  private readonly base: string

  constructor(base: string = API_BASE) {
    this.base = base
  }

  /**
   * Read one thing.
   *
   * A read needs no token: the service asks for the token only on a request
   * that changes something, which is what lets the workbench draw the whole
   * task before it has a token to draw it with.
   */
  async get<T>(path: string): Promise<T> {
    if (path === API_PATHS.session) {
      throw new Error(
        'the session response carries the token; read the session with sessionPath() ' +
          'rather than putting the token in a value a caller can hold.',
      )
    }
    return this.exchange<T>('GET', path)
  }

  /**
   * Change one thing.
   *
   * A change presents the session token, and the token goes in the header and
   * nowhere else.
   */
  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.exchange<T>('POST', path, body)
  }

  /**
   * Where the service wrote the session token.
   *
   * The path is returned and the token is not: the token goes into the
   * module-level holder, where React cannot see it.
   */
  async sessionPath(): Promise<string> {
    const info = await this.fetchSession()
    holdSessionToken(info.token)
    return info.path
  }

  /** The service's own session response, read once and kept private. */
  private async fetchSession(): Promise<SessionInfo> {
    const response = await this.send('GET', API_PATHS.session)
    return this.read<SessionInfo>(response)
  }

  /**
   * The token this client presents, asking for it if it holds none.
   *
   * The session is fetched over the same origin, which is the only place it
   * can be fetched from: the service refuses a request whose origin is not
   * its own, and a page on another site cannot be at that origin.
   */
  private async token(): Promise<string> {
    const held = sessionToken()
    if (held !== null) {
      return held
    }
    const info = await this.fetchSession()
    holdSessionToken(info.token)
    return info.token
  }

  /** One request, and one retry when the token was the thing that was refused. */
  private async exchange<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
    const response = await this.send(method, path, body)
    if (response.status === 401) {
      // The service refused the token. It may have restarted and minted a new
      // one, so the old one is forgotten and the request is made once more
      // with the new one. One retry, not a loop: a service that refuses the
      // fresh token too is a service that is refusing, and a loop would be a
      // request storm against a service that has already said no.
      forgetSessionToken()
      await this.token()
      const retried = await this.send(method, path, body)
      return this.read<T>(retried)
    }
    return this.read<T>(response)
  }

  /** The request itself. */
  private async send(method: 'GET' | 'POST', path: string, body?: unknown): Promise<Response> {
    assertRelativePath(path)
    const headers: Record<string, string> = {}
    if (method === 'POST') {
      headers['Authorization'] = `Bearer ${await this.token()}`
      headers['Content-Type'] = 'application/json'
    }
    const init: RequestInit = {
      method,
      headers,
      // No cookies. The service's session is the header token, and a cookie
      // the browser happened to carry would be a credential this page did
      // not mean to present.
      credentials: 'omit',
      // The page's own address is not something to leak either.
      referrerPolicy: 'no-referrer',
    }
    if (body !== undefined) {
      init.body = JSON.stringify(body)
    }
    return await fetch(apiUrl(path, this.base), init)
  }

  /** A response, or the failure it describes. */
  private async read<T>(response: Response): Promise<T> {
    if (response.ok) {
      const payload = await readJson(response)
      return payload as T
    }
    const payload = await readJson(response).catch(() => null)
    if (isRefusalBody(payload)) {
      throw new ApiRefusal(payload)
    }
    throw new ApiFailure(
      response.status,
      `the service answered ${response.status} ${response.statusText} for this request.`,
      payload,
    )
  }
}

/** The client the workbench reads through. */
export const api = new LabCairnClient()
