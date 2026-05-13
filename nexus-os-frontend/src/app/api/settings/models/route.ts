import { NextResponse } from 'next/server';

// GET /api/settings/models - Retrieve current model assignments
export async function GET() {
  try {
    // In a real implementation, this would fetch from a database
    // For now, return sample data
    const settings = {
      supervisor_model: "qwen2.5-coder:14b",
      embedding_model: "bge-m3:latest",
      vision_model: "llava:13b",
      reranker_model: "mxbai-rerank:large"
    };
    
    return NextResponse.json(settings);
  } catch (error) {
    return NextResponse.json(
      { error: 'Failed to fetch model settings' },
      { status: 500 }
    );
  }
}

// POST /api/settings/models - Update model assignments and trigger reload
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { supervisor_model, embedding_model, vision_model, reranker_model } = body;
    
    // In a real implementation, this would:
    // 1. Save to database
    // 2. Trigger backend reload via webhook or API call
    // 3. Return updated settings
    
    console.log('Updating model settings:', {
      supervisor_model,
      embedding_model,
      vision_model,
      reranker_model
    });
    
    // Simulate backend processing
    return NextResponse.json({
      status: 'success',
      message: 'Model settings updated. Backend will reload on next request.',
      supervisor_model,
      embedding_model,
      vision_model,
      reranker_model,
      timestamp: new Date().toISOString()
    });
  } catch (error) {
    return NextResponse.json(
      { 
        status: 'error', 
        message: error instanceof Error ? error.message : 'Failed to update settings'
      },
      { status: 500 }
    );
  }
}