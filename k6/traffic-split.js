
import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

// Count responses served by each application version
const stableResponses = new Counter('stable_responses');
const canaryResponses = new Counter('canary_responses');
const unknownResponses = new Counter('unknown_version_responses');

const BASE_URL = __ENV.BASE_URL || 'http://orders-haproxy.test';

const STABLE_VERSION = __ENV.STABLE_VERSION || 'v4';
const CANARY_VERSION = __ENV.CANARY_VERSION || 'v5';

export const options = {
  scenarios: {
    traffic_split: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.RATE || 10),
      timeUnit: '1s',
      duration: __ENV.DURATION || '60s',
      preAllocatedVUs: 5,
      maxVUs: 20,
    },
  },

  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
    checks: ['rate>0.99'],
    dropped_iterations: ['count==0'],
    unknown_version_responses: ['count==0'],
  },
};

export default function () {
  const response = http.get(`${BASE_URL}/version`, {
    timeout: '5s',
  });

  let version = 'unknown';

  try {
    const body = response.json();
    if (body && typeof body.version === 'string') {
      version = body.version;
    }
  } catch (_) {
    version = 'unknown';
  }

  check(response, {
    'HTTP status is 200': (r) => r.status === 200,
    'version field exists': () => version !== 'unknown',
  });

  if (response.status === 200 && version === STABLE_VERSION) {
    stableResponses.add(1);
  } else if (response.status === 200 && version === CANARY_VERSION) {
    canaryResponses.add(1);
  } else {
    unknownResponses.add(1);
  }
}
