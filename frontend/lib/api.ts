function normaliseBase(url: string | undefined): string | undefined {
  if (!url) return undefined;
  return url.replace(/\/$/, '');
}

async function executeRequest(url: string, options: RequestInit, headers: Headers) {
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const message = typeof body?.detail === 'string' ? body.detail : 'Ошибка запроса';
    const error = new Error(message);
    // Attach status to error for retry logic downstream
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }

  if (response.status === 204 || response.status === 205) {
    return null;
  }

  return response.json();
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const isBrowser = typeof window !== 'undefined';
  const token = isBrowser ? window.localStorage.getItem('tuberry_token') : null;

  const headers = new Headers(options.headers ?? {});
  const bodyProvided = options.body !== undefined && options.body !== null;
  const isFormData = typeof FormData !== 'undefined' && bodyProvided && options.body instanceof FormData;
  const isJsonString = typeof options.body === 'string';
  if (bodyProvided && isJsonString && !isFormData && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const sanitizedPath = path.startsWith('/') ? path : `/${path}`;
  const envBrowserBase = normaliseBase(process.env.NEXT_PUBLIC_API_URL);
  const internalBase = normaliseBase(process.env.NEXT_INTERNAL_API_URL) || 'http://backend:8000';

  const preferredTargets: string[] = [];

  if (isBrowser) {
    // 1. Same-origin request (avoids mixed content issues and reuses proxy if configured)
    preferredTargets.push(sanitizedPath);

    // 2. Explicit browser base if задан
    if (envBrowserBase) {
      preferredTargets.push(`${envBrowserBase}${sanitizedPath}`);
    }

    // 3. Optional localhost fallback (only безопасно для http сред)
    const isSecure = window.location.protocol === 'https:';
    const hostname = window.location.hostname;
    const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1';
    if (!isSecure) {
      const fallbackPort =
        process.env.NEXT_PUBLIC_API_FALLBACK_PORT || (window.location.port && window.location.port !== '3000' ? window.location.port : '8080');
      const fallbackBrowserBase = normaliseBase(`${window.location.protocol}//${hostname}:${fallbackPort}`);
      if (fallbackBrowserBase) {
        if (!preferredTargets.includes(`${fallbackBrowserBase}${sanitizedPath}`)) {
          preferredTargets.push(`${fallbackBrowserBase}${sanitizedPath}`);
        }
      }
    } else if (isSecure && isLocalHost) {
      // В dev через https на localhost используем http fallback только если явно указано в переменной окружения
      const httpsFallback = process.env.NEXT_PUBLIC_API_HTTPS_FALLBACK && normaliseBase(process.env.NEXT_PUBLIC_API_HTTPS_FALLBACK);
      if (httpsFallback) {
        preferredTargets.push(`${httpsFallback}${sanitizedPath}`);
      }
    }
  } else {
    preferredTargets.push(`${internalBase}${sanitizedPath}`);
  }

  if (preferredTargets.length === 0) {
    preferredTargets.push(`${envBrowserBase || internalBase}${sanitizedPath}`);
  }

  const uniqueTargets = Array.from(new Set(preferredTargets));
  let lastError: Error | null = null;

  for (const target of uniqueTargets) {
    try {
      return await executeRequest(target, options, headers);
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Ошибка запроса');
      const status = (error as Error & { status?: number }).status;

      if (isBrowser && status === 401) {
        try {
          window.localStorage.removeItem('tuberry_token');
        } catch (storageError) {
          console.warn('Не удалось очистить токен из localStorage', storageError);
        }
        const redirectTarget = path.startsWith('/admin') ? '/admin/login' : '/login';
        window.location.href = redirectTarget;
        lastError = error;
        break;
      }

      const canRetry = status && status >= 500 && uniqueTargets.length > 1 && target !== uniqueTargets[uniqueTargets.length - 1];
      if (!canRetry && !(err instanceof TypeError && uniqueTargets.length > 1)) {
        throw error;
      }
      lastError = error;
    }
  }

  if (lastError) {
    throw lastError;
  }

  throw new Error('Ошибка запроса');
}
