import { FullAuditRequest, FullAuditResponse, ProgressStep } from './types';


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://reelclaim-api.onrender.com';

const RETRY_DELAYS_MS = [3000, 5000, 8000, 10000]; // 3s, 5s, 8s, 10s (cumulative ~26s window)

export async function auditReel(
  captionOrOptions: string | { caption?: string; video_url?: string; override_url?: string; gemini_api_key?: string; youtube_api_key?: string },
  overrideUrl?: string,
  geminiApiKey?: string,
  onStepChange?: (step: ProgressStep, details?: { retryAttempt?: number; maxRetries?: number; nextDelaySec?: number }) => void
): Promise<FullAuditResponse> {
  if (onStepChange) onStepChange('extracting');

  let payload: FullAuditRequest;
  if (typeof captionOrOptions === 'object') {
    payload = {
      caption: captionOrOptions.caption,
      video_url: captionOrOptions.video_url,
      override_url: captionOrOptions.override_url,
      gemini_api_key: captionOrOptions.gemini_api_key,
      youtube_api_key: captionOrOptions.youtube_api_key,
    };
  } else {
    payload = {
      caption: captionOrOptions,
      override_url: overrideUrl && overrideUrl.trim().length > 0 ? overrideUrl.trim() : undefined,
      gemini_api_key: geminiApiKey && geminiApiKey.trim().length > 0 ? geminiApiKey.trim() : undefined,
    };
  }


  const executeRequest = async (): Promise<FullAuditResponse> => {
    const response = await fetch(`${API_BASE_URL}/audit-reel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Server returned error status ${response.status}`);
    }

    return await response.json();
  };

  // Step feedback timer during initial extraction / crawl
  let currentStepState: ProgressStep = 'extracting';
  const stepTimer1 = setTimeout(() => {
    if (currentStepState === 'extracting') {
      currentStepState = 'crawling';
      if (onStepChange) onStepChange('crawling');
    }
  }, 2500);

  const stepTimer2 = setTimeout(() => {
    if (currentStepState === 'crawling') {
      currentStepState = 'cross_checking';
      if (onStepChange) onStepChange('cross_checking');
    }
  }, 8000);

  try {
    let result = await executeRequest();
    clearTimeout(stepTimer1);
    clearTimeout(stepTimer2);

    // If initial response indicates browser concurrency lock is busy, initiate progressive backoff retries
    let attempt = 0;
    while (result.crawl_status === 'busy' && attempt < RETRY_DELAYS_MS.length) {
      const delayMs = RETRY_DELAYS_MS[attempt];
      const nextDelaySec = Math.round(delayMs / 1000);
      attempt++;

      if (onStepChange) {
        onStepChange('crawling_busy', {
          retryAttempt: attempt,
          maxRetries: RETRY_DELAYS_MS.length,
          nextDelaySec,
        });
      }

      await new Promise((resolve) => setTimeout(resolve, delayMs));

      if (onStepChange) onStepChange('crawling');
      result = await executeRequest();
    }

    return result;
  } catch (err: any) {
    clearTimeout(stepTimer1);
    clearTimeout(stepTimer2);
    throw new Error(err.message || 'Failed to connect to ReelClaim audit service');
  }
}

export async function fetchAuditById(auditId: string): Promise<FullAuditResponse> {
  const response = await fetch(`${API_BASE_URL}/audits/${auditId}`);
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to fetch audit #${auditId}`);
  }
  return await response.json();
}

export async function submitAuditFeedback(
  auditId: string,
  feedback: import('./types').FeedbackRequest,
  submitterToken?: string | null
): Promise<import('./types').FeedbackResponse> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (submitterToken) {
    headers['X-Submitter-Token'] = submitterToken;
  }

  const response = await fetch(`${API_BASE_URL}/audits/${auditId}/feedback`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      ...feedback,
      submitter_token: submitterToken || feedback.submitter_token || undefined,
    }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || `Failed to submit feedback (${response.status})`);
  }

  return await response.json();
}



