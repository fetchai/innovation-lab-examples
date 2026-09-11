// Test setup file for Jest
// This file runs before each test file

// Set longer timeout for performance tests
jest.setTimeout(30000);

// Mock environment variables
process.env.NODE_ENV = 'test';
process.env.GOOGLE_MAPS_API_KEY = 'test-api-key';

// Console suppression for cleaner test output
const originalConsoleError = console.error;
const originalConsoleWarn = console.warn;

beforeEach(() => {
  // Suppress console errors/warnings during tests unless debugging
  if (!process.env.DEBUG_TESTS) {
    console.error = jest.fn();
    console.warn = jest.fn();
  }
});

afterEach(() => {
  // Restore console functions
  console.error = originalConsoleError;
  console.warn = originalConsoleWarn;

  // Clear all mocks after each test
  jest.clearAllMocks();
});

// Export utilities instead of adding to global
export const createMockLocation = (lat = 37.7749, lng = -122.4194) => ({
  latitude: lat,
  longitude: lng,
});

export const createMockRestaurant = (
  overrides: Record<string, unknown> = {}
) => ({
  placeId: 'test-place',
  name: 'Test Restaurant',
  address: '123 Test Street',
  location: { latitude: 37.7749, longitude: -122.4194 },
  rating: 4.5,
  userRatingsTotal: 100,
  priceLevel: 2,
  cuisineTypes: ['Italian'],
  googleMapsUrl: 'https://maps.google.com/test',
  ...overrides,
});

// Performance monitoring helpers
export const measureExecutionTime = async (fn: () => Promise<unknown>) => {
  const startTime = Date.now();
  const result = await fn();
  const duration = Date.now() - startTime;
  return { result, duration };
};

// Memory usage helpers
export const getMemoryUsage = () => {
  const usage = process.memoryUsage();
  return {
    heapUsed: Math.round(usage.heapUsed / 1024 / 1024), // MB
    heapTotal: Math.round(usage.heapTotal / 1024 / 1024), // MB
    external: Math.round(usage.external / 1024 / 1024), // MB
    rss: Math.round(usage.rss / 1024 / 1024), // MB
  };
};

/**
 * Enable garbage collection for memory leak tests
 *
 * The global.gc function is only available when Node.js is started with --expose-gc flag.
 * In testing environments, we provide a no-op fallback to avoid runtime errors.
 *
 * Note: @types/node defines gc as NodeJS.GCFunction which can return Promise<void>,
 * but the actual implementation can be synchronous. We provide a compatible fallback.
 */
if (typeof global.gc === 'undefined') {
  // Type assertion is necessary here because we're providing a fallback implementation
  // for the gc function when it's not exposed via --expose-gc flag
  global.gc = (() => {
    // No-op fallback when garbage collection is not exposed
    // In CI/testing environments without --expose-gc flag
  }) as NodeJS.GCFunction;
}
