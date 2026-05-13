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
    const response = await fetch(`${baseUrl}/models`);
    
    if (!response.ok) {
      return NextResponse.json(
        { models: [], loaded: [], error: `Failed to fetch models: ${response.status}` },
        { status: 200 }
      );
    }
    
    const data = await response.json();
    
    return NextResponse.json({
      models: data.data || [],
      loaded: data.data?.map((m: any) => m.id) || []
    });
  } catch (error) {
    return NextResponse.json(
      { 
        models: [], 
        loaded: [],
        error: error instanceof Error ? error.message : 'Failed to connect'
      },
      { status: 200 }
    );
  }
}