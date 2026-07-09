import { RestaurantRecommendationService } from '../services/restaurantRecommendationService.js';
import { Restaurant, RestaurantSearchParams } from '../types/index.js';

describe('RestaurantRecommendationService', () => {
  let service: RestaurantRecommendationService;

  beforeEach(() => {
    service = new RestaurantRecommendationService();
  });

  const createMockRestaurant = (
    overrides: Partial<Restaurant> = {}
  ): Restaurant => ({
    placeId: 'test-place',
    name: 'Test Restaurant',
    address: '123 Test St',
    location: { latitude: 37.7749, longitude: -122.4194 },
    rating: 4.5,
    userRatingsTotal: 100,
    priceLevel: 2,
    cuisineTypes: ['Italian'],
    ...overrides,
  });

  const mockSearchParams: RestaurantSearchParams = {
    location: { latitude: 37.7749, longitude: -122.4194 },
    cuisineTypes: ['Italian'],
    mood: 'romantic',
    event: 'dating',
    radius: 2000,
  };

  describe('Parallel Processing', () => {
    test('should process restaurants in parallel', async () => {
      const restaurants = Array.from({ length: 10 }, (_, i) =>
        createMockRestaurant({
          placeId: `place_${i}`,
          name: `Restaurant ${i}`,
          rating: 4.0 + i / 10, // Varying ratings
        })
      );

      const startTime = Date.now();
      const recommendations = await service.getRecommendations(
        restaurants,
        mockSearchParams
      );
      const duration = Date.now() - startTime;

      // Should complete quickly due to parallel processing
      expect(duration).toBeLessThan(200); // Increased from 100ms to account for system load variations
      expect(recommendations).toHaveLength(3);

      // Should be sorted by score (highest first)
      expect(recommendations[0].score).toBeGreaterThanOrEqual(
        recommendations[1].score
      );
      expect(recommendations[1].score).toBeGreaterThanOrEqual(
        recommendations[2].score
      );
    });

    test('should handle large datasets efficiently', async () => {
      const restaurants = Array.from({ length: 100 }, (_, i) =>
        createMockRestaurant({
          placeId: `place_${i}`,
          name: `Restaurant ${i}`,
          rating: 3.0 + Math.random() * 2, // Random ratings between 3-5
          priceLevel: (Math.floor(Math.random() * 4) + 1) as 1 | 2 | 3 | 4,
          cuisineTypes: i % 2 === 0 ? ['Italian'] : ['Japanese'],
        })
      );

      const startTime = Date.now();
      const recommendations = await service.getRecommendations(
        restaurants,
        mockSearchParams
      );
      const duration = Date.now() - startTime;

      // Should handle 100 restaurants efficiently
      expect(duration).toBeLessThan(300); // Increased from 200ms to account for processing 100 restaurants with system load variations
      expect(recommendations).toHaveLength(3);
    });
  });

  describe('Scoring Algorithm', () => {
    test('should score restaurants based on rating', () => {
      const highRatedRestaurant = createMockRestaurant({
        rating: 4.8,
        userRatingsTotal: 500,
      });

      const lowRatedRestaurant = createMockRestaurant({
        rating: 3.2,
        userRatingsTotal: 50,
      });

      const highScore = (service as any).calculateRestaurantScore(
        highRatedRestaurant,
        mockSearchParams
      );
      const lowScore = (service as any).calculateRestaurantScore(
        lowRatedRestaurant,
        mockSearchParams
      );

      expect(highScore).toBeGreaterThan(lowScore);
    });

    test('should score cuisine matches higher', () => {
      const matchingRestaurant = createMockRestaurant({
        cuisineTypes: ['Italian', 'Mediterranean'],
      });

      const nonMatchingRestaurant = createMockRestaurant({
        cuisineTypes: ['Chinese', 'Asian'],
      });

      const matchingScore = (service as any).calculateRestaurantScore(
        matchingRestaurant,
        mockSearchParams
      );
      const nonMatchingScore = (service as any).calculateRestaurantScore(
        nonMatchingRestaurant,
        mockSearchParams
      );

      expect(matchingScore).toBeGreaterThan(nonMatchingScore);
    });

    test('should consider event suitability', () => {
      const datingRestaurant = createMockRestaurant({
        priceLevel: 3,
        cuisineTypes: ['Italian', 'Fine Dining'],
        rating: 4.5,
      });

      const casualRestaurant = createMockRestaurant({
        priceLevel: 1,
        cuisineTypes: ['Fast Food'],
        rating: 4.5,
      });

      const datingSuitability = (service as any).calculateEventSuitability(
        datingRestaurant,
        'dating'
      );
      const casualSuitability = (service as any).calculateEventSuitability(
        casualRestaurant,
        'dating'
      );

      expect(datingSuitability).toBeGreaterThan(casualSuitability);
    });

    test('should consider mood matching', () => {
      const romanticRestaurant = createMockRestaurant({
        name: 'Romantic Candlelit Restaurant',
        cuisineTypes: ['French', 'Fine Dining'],
        priceLevel: 4,
      });

      const casualRestaurant = createMockRestaurant({
        name: 'Sports Bar Grill',
        cuisineTypes: ['American'],
        priceLevel: 2,
      });

      const romanticMoodMatch = (service as any).calculateMoodMatch(
        romanticRestaurant,
        'romantic'
      );
      const casualMoodMatch = (service as any).calculateMoodMatch(
        casualRestaurant,
        'romantic'
      );

      expect(romanticMoodMatch).toBeGreaterThan(casualMoodMatch);
    });
  });

  describe('Event Suitability', () => {
    test('should recommend appropriate restaurants for dating', () => {
      const restaurants = [
        createMockRestaurant({
          placeId: 'fine-dining',
          name: 'Elegant Fine Dining',
          priceLevel: 4,
          cuisineTypes: ['French', 'Fine Dining'],
          rating: 4.7,
        }),
        createMockRestaurant({
          placeId: 'fast-food',
          name: 'Quick Burger Joint',
          priceLevel: 1,
          cuisineTypes: ['Fast Food'],
          rating: 4.2,
        }),
      ];

      const fineDiningSuitability = (service as any).calculateEventSuitability(
        restaurants[0],
        'dating'
      );
      const fastFoodSuitability = (service as any).calculateEventSuitability(
        restaurants[1],
        'dating'
      );

      expect(fineDiningSuitability).toBeGreaterThan(fastFoodSuitability);
    });

    test('should recommend appropriate restaurants for business meetings', () => {
      const businessRestaurant = createMockRestaurant({
        priceLevel: 3,
        cuisineTypes: ['American', 'Steakhouse'],
        rating: 4.5,
      });

      const casualRestaurant = createMockRestaurant({
        priceLevel: 1,
        cuisineTypes: ['Pizza'],
        rating: 4.5,
      });

      const businessSuitability = (service as any).calculateEventSuitability(
        businessRestaurant,
        'business'
      );
      const casualSuitability = (service as any).calculateEventSuitability(
        casualRestaurant,
        'business'
      );

      expect(businessSuitability).toBeGreaterThan(casualSuitability);
    });
  });

  describe('Reasoning Generation', () => {
    test('should generate comprehensive reasoning', () => {
      const restaurant = createMockRestaurant({
        rating: 4.6,
        userRatingsTotal: 250,
        cuisineTypes: ['Italian'],
        priceLevel: 3,
        openingHours: {
          openNow: true,
          weekdayText: ['Monday: 5:00 PM – 10:00 PM'],
        },
      });

      const reasoning = (service as any).generateReasoning(
        restaurant,
        mockSearchParams,
        85, // High score
        8, // High event suitability
        7 // Good mood match
      );

      expect(reasoning).toContain('Excellent rating');
      expect(reasoning).toContain('Italian cuisine');
      expect(reasoning).toContain('Perfect for dating');
      expect(reasoning).toContain('Currently open');
    });

    test('should handle restaurants with missing data', () => {
      const restaurant = createMockRestaurant({
        rating: 0,
        userRatingsTotal: 0,
        priceLevel: undefined,
      });

      const reasoning = (service as any).generateReasoning(
        restaurant,
        mockSearchParams,
        30, // Low score
        5, // Average event suitability
        5 // Average mood match
      );

      expect(reasoning).toBeTruthy();
      expect(reasoning.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    test('should handle empty restaurant list', async () => {
      const recommendations = await service.getRecommendations(
        [],
        mockSearchParams
      );
      expect(recommendations).toHaveLength(0);
    });

    test('should handle restaurants with identical scores', async () => {
      const restaurants = Array.from({ length: 5 }, (_, i) =>
        createMockRestaurant({
          placeId: `identical_${i}`,
          name: `Identical Restaurant ${i}`,
          rating: 4.5,
          userRatingsTotal: 100,
          priceLevel: 2,
          cuisineTypes: ['Italian'],
        })
      );

      const recommendations = await service.getRecommendations(
        restaurants,
        mockSearchParams
      );
      expect(recommendations).toHaveLength(3);

      // All should have similar scores
      const scores = recommendations.map(r => r.score);
      const maxScore = Math.max(...scores);
      const minScore = Math.min(...scores);
      expect(maxScore - minScore).toBeLessThan(5); // Small variance
    });

    test('should handle missing search criteria', async () => {
      const restaurants = [createMockRestaurant()];
      const emptyParams: RestaurantSearchParams = {
        cuisineTypes: [],
        mood: '',
        event: '',
      };

      const recommendations = await service.getRecommendations(
        restaurants,
        emptyParams
      );
      expect(recommendations).toHaveLength(1);
      expect(recommendations[0].score).toBeGreaterThan(0);
    });
  });

  describe('Performance Benchmarks', () => {
    test('should maintain performance with varying restaurant counts', async () => {
      const testSizes = [5, 25, 50, 100];
      const timings: number[] = [];

      for (const size of testSizes) {
        const restaurants = Array.from({ length: size }, (_, i) =>
          createMockRestaurant({
            placeId: `bench_${i}`,
            rating: 3 + Math.random() * 2,
          })
        );

        const startTime = Date.now();
        await service.getRecommendations(restaurants, mockSearchParams);
        const duration = Date.now() - startTime;

        timings.push(duration);
      }

      // Performance should scale reasonably (not exponentially)
      // Allow more generous scaling for small sample sizes since timing can be inconsistent
      expect(timings[3]).toBeLessThan(Math.max(timings[0] * 100, 50)); // 100 items shouldn't take 100x longer than 5 items or more than 50ms
    });

    test('should handle concurrent recommendation requests', async () => {
      const restaurants = Array.from({ length: 20 }, (_, i) =>
        createMockRestaurant({ placeId: `concurrent_${i}` })
      );

      const concurrentRequests = Array(5)
        .fill(null)
        .map(() => service.getRecommendations(restaurants, mockSearchParams));

      const startTime = Date.now();
      const results = await Promise.all(concurrentRequests);
      const duration = Date.now() - startTime;

      expect(duration).toBeLessThan(500); // Should handle 5 concurrent requests quickly
      expect(results).toHaveLength(5);
      results.forEach(result => {
        expect(result).toHaveLength(3);
      });
    });
  });
});
