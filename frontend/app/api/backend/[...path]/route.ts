import { NextRequest, NextResponse } from 'next/server';

const BACKEND_BASE = process.env.NEXT_INTERNAL_API_URL?.replace(/\/$/, '') || 'http://backend:8000';

async function proxyRequest(request: NextRequest, path: string[]) {
  const search = request.nextUrl.search;
  const targetPath = `/${path.join('/')}`.replace(/\/+/g, '/');
  const targetUrl = `${BACKEND_BASE}${targetPath}${search}`;

  const headers = new Headers(request.headers);
  headers.set('host', new URL(BACKEND_BASE).host);
  headers.delete('content-length');

  let body: BodyInit | undefined;
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const contentType = request.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await request.json();
      body = JSON.stringify(data);
      headers.set('content-type', 'application/json');
    } else if (contentType.includes('application/x-www-form-urlencoded')) {
      const form = await request.formData();
      body = new URLSearchParams(Array.from(form.entries()) as [string, string][]);
    } else if (contentType.includes('multipart/form-data')) {
      const form = await request.formData();
      body = form;
    } else {
      body = await request.text();
    }
  }

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
  return proxyRequest(request, context.params.path);
}

export async function POST(request: NextRequest, context: { params: { path: string[] } }) {
  return proxyRequest(request, context.params.path);
}

export async function PUT(request: NextRequest, context: { params: { path: string[] } }) {
  return proxyRequest(request, context.params.path);
}

export async function PATCH(request: NextRequest, context: { params: { path: string[] } }) {
  return proxyRequest(request, context.params.path);
}

export async function DELETE(request: NextRequest, context: { params: { path: string[] } }) {
  return proxyRequest(request, context.params.path);
}
