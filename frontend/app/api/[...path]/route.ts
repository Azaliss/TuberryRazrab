import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.NEXT_INTERNAL_API_URL?.replace(/\/$/, '') || 'http://backend:8000';

function buildTargetUrl(pathSegments: string[], search: string): string {
  const suffix = pathSegments.length ? `/${pathSegments.join('/')}` : '';
  const path = `/api${suffix}`;
  return `${BACKEND_BASE}${path}${search}`;
}

async function readRequestBody(request: NextRequest): Promise<BodyInit | undefined> {
  if (request.method === 'GET' || request.method === 'HEAD') {
    return undefined;
  }

  const contentType = request.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    const data = await request.json();
    return JSON.stringify(data);
  }

  if (contentType.includes('application/x-www-form-urlencoded')) {
    const form = await request.formData();
    return new URLSearchParams(Array.from(form.entries()) as [string, string][]);
  }

  if (contentType.includes('multipart/form-data')) {
    return request.formData();
  }

  return request.text();
}

async function proxy(request: NextRequest, pathSegments: string[]) {
  const targetUrl = buildTargetUrl(pathSegments, request.nextUrl.search);

  const headers = new Headers(request.headers);
  headers.set('host', new URL(BACKEND_BASE).host);
  headers.delete('content-length');

  const body = await readRequestBody(request);

  const backendResponse = await fetch(targetUrl, {
    method: request.method,
    headers,
    body,
    redirect: 'manual',
  });

  const responseHeaders = new Headers(backendResponse.headers);
  responseHeaders.delete('content-encoding');
  responseHeaders.delete('content-length');

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    statusText: backendResponse.statusText,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: { params: { path: string[] } }) {
  return proxy(request, context.params.path ?? []);
}

export async function POST(request: NextRequest, context: { params: { path: string[] } }) {
  return proxy(request, context.params.path ?? []);
}

export async function PUT(request: NextRequest, context: { params: { path: string[] } }) {
  return proxy(request, context.params.path ?? []);
}

export async function PATCH(request: NextRequest, context: { params: { path: string[] } }) {
  return proxy(request, context.params.path ?? []);
}

export async function DELETE(request: NextRequest, context: { params: { path: string[] } }) {
  return proxy(request, context.params.path ?? []);
}

export const dynamic = 'force-dynamic';
