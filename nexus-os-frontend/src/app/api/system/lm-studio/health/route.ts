import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const baseUrl = searchParams.get('baseUrl');
  
  if (!baseUrl) {
    return NextResponse.json(
      { error: 'baseUrl parameter is required' },
      { status: 400 }
    );
  }
  
  try {
    const response = await fetch(`${baseUrl}/health`);
    
    if (!response.ok) {
      return NextResponse.json(
        { status: 'error', message: `LM Studio returned ${response.status}` },
        { status: 200 }
      );
    }
    
    return NextResponse.json({ status: 'ok' });
  } catch (error) {
    return NextResponse.json(
      { 
        status: 'error', 
        message: error instanceof Error ? error.message : 'Connection failed'
      },
      { status: 200 }
    );
  }
}