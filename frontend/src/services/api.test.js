import { afterEach, expect, test, vi } from 'vitest'
import { apiRequest } from './api'

afterEach(() => vi.unstubAllGlobals())

test('builds a versioned API URL from a relative endpoint path', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: vi.fn().mockResolvedValue({ id: 'profile-id' }),
  })
  vi.stubGlobal('fetch', fetchMock)

  await apiRequest('/auth/me', {}, 'test-access-token')

  expect(fetchMock).toHaveBeenCalledWith(
    'http://localhost:8000/api/v1/auth/me',
    expect.objectContaining({
      headers: expect.objectContaining({
        Accept: 'application/json',
        Authorization: 'Bearer test-access-token',
      }),
    }),
  )
})

test('surfaces a FastAPI detail message and preserves the HTTP status', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    status: 409,
    json: vi.fn().mockResolvedValue({ detail: 'Requested slot is unavailable.' }),
  }))

  await expect(apiRequest('/appointments')).rejects.toMatchObject({
    message: 'Requested slot is unavailable.',
    status: 409,
  })
})

test('uses a status fallback when an error response has no usable JSON detail', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: false,
    status: 502,
    json: vi.fn().mockRejectedValue(new SyntaxError('not json')),
  }))

  await expect(apiRequest('/appointments')).rejects.toMatchObject({
    message: 'API request failed with status 502',
    status: 502,
  })
})
