import {
  Restaurant,
  RestaurantSearchParams,
  RestaurantRecommendation,
} from '../types/index.js';

export class RestaurantRecommendationService {
  /**
   * Analyze and score restaurants based on search criteria
   * Optimized with parallel processing
   */
  async getRecommendations(
    restaurants: Restaurant[],
    params: RestaurantSearchParams
  ): Promise<RestaurantRecommendation[]> {
    // Apply strict cuisine filtering if requested
    let filteredRestaurants = restaurants;
    if (params.strictCuisineFiltering && params.cuisineTypes.length > 0) {
      filteredRestaurants = restaurants.filter(restaurant => 
        this.calculateCuisineMatch(restaurant, params.cuisineTypes) > 0
      );
      
      // If no restaurants match the strict criteria, fall back to all restaurants
      // with a warning that no exact matches were found
      if (filteredRestaurants.length === 0) {
        console.warn('No restaurants found matching strict cuisine criteria, falling back to all results');
        filteredRestaurants = restaurants;
      }
    }

    // Process all restaurants in parallel for better performance
    const recommendationPromises = filteredRestaurants.map(async restaurant => {
      const [score, suitabilityForEvent, moodMatch] = await Promise.all([
        // These can run in parallel since they're independent calculations
        Promise.resolve(this.calculateRestaurantScore(restaurant, params)),
        Promise.resolve(
          this.calculateEventSuitability(restaurant, params.event)
        ),
        Promise.resolve(this.calculateMoodMatch(restaurant, params.mood)),
      ]);

      const reasoning = this.generateReasoning(
        restaurant,
        params,
        score,
        suitabilityForEvent,
        moodMatch
      );

      return {
        restaurant,
        score,
        reasoning,
        suitabilityForEvent,
        moodMatch,
      };
    });

    const recommendations = await Promise.all(recommendationPromises);

    // Sort by score (highest first) and return top 3
    return recommendations.sort((a, b) => b.score - a.score).slice(0, 3);
  }

  /**
   * Calculate overall score for a restaurant based on multiple factors
   */
  private calculateRestaurantScore(
    restaurant: Restaurant,
    params: RestaurantSearchParams
  ): number {
    let score = 0;
    let factors = 0;

    // Rating factor (40% weight)
    if (restaurant.rating > 0) {
      score += (restaurant.rating / 5) * 40;
      factors++;
    }

    // Review count factor (20% weight) - more reviews = more reliable
    if (restaurant.userRatingsTotal > 0) {
      const reviewScore = Math.min(restaurant.userRatingsTotal / 100, 1) * 20;
      score += reviewScore;
      factors++;
    }

    // Cuisine match factor (20% weight)
    const cuisineMatch = this.calculateCuisineMatch(
      restaurant,
      params.cuisineTypes
    );
    score += cuisineMatch * 20;
    factors++;

    // Event suitability factor (10% weight)
    const eventSuitability = this.calculateEventSuitability(
      restaurant,
      params.event
    );
    score += (eventSuitability / 10) * 10;
    factors++;

    // Mood match factor (10% weight)
    const moodMatch = this.calculateMoodMatch(restaurant, params.mood);
    score += (moodMatch / 10) * 10;
    factors++;

    return factors > 0 ? score : 0;
  }

  /**
   * Calculate how well restaurant cuisine matches search criteria
   */
  private calculateCuisineMatch(
    restaurant: Restaurant,
    searchCuisines: string[]
  ): number {
    if (searchCuisines.length === 0) return 1; // No specific cuisine preference

    const restaurantCuisines = restaurant.cuisineTypes.map(c =>
      c.toLowerCase()
    );
    const searchCuisinesLower = searchCuisines.map(c => c.toLowerCase());

    let matches = 0;
    for (const searchCuisine of searchCuisinesLower) {
      for (const restaurantCuisine of restaurantCuisines) {
        if (
          restaurantCuisine.includes(searchCuisine) ||
          searchCuisine.includes(restaurantCuisine)
        ) {
          matches++;
          break;
        }
      }
    }

    return matches / searchCuisines.length;
  }

  /**
   * Calculate suitability for specific events (1-10 scale)
   */
  private calculateEventSuitability(
    restaurant: Restaurant,
    event: string
  ): number {
    const eventFactors = {
      dating: {
        preferredPriceLevel: [2, 3, 4], // Mid to high-end
        preferredCuisines: [
          'italian',
          'french',
          'japanese',
          'mediterranean',
          'fine dining',
        ],
        avoidCuisines: ['fast food', 'buffet'],
        minRating: 4.0,
        atmosphereKeywords: ['romantic', 'intimate', 'cozy', 'elegant'],
      },
      gathering: {
        preferredPriceLevel: [1, 2, 3], // Budget to mid-range
        preferredCuisines: [
          'american',
          'italian',
          'chinese',
          'mexican',
          'pizza',
        ],
        avoidCuisines: ['fine dining'],
        minRating: 3.5,
        atmosphereKeywords: ['family-friendly', 'spacious', 'casual', 'kids'],
      },
      business: {
        preferredPriceLevel: [2, 3, 4], // Mid to high-end
        preferredCuisines: ['american', 'italian', 'steakhouse', 'seafood'],
        avoidCuisines: ['fast food', 'buffet'],
        minRating: 4.0,
        atmosphereKeywords: ['quiet', 'professional', 'upscale', 'private'],
      },
      casual: {
        preferredPriceLevel: [1, 2], // Budget to mid-range
        preferredCuisines: ['american', 'pizza', 'cafe', 'mexican', 'asian'],
        avoidCuisines: [],
        minRating: 3.0,
        atmosphereKeywords: ['casual', 'relaxed', 'friendly'],
      },
      celebration: {
        preferredPriceLevel: [3, 4], // High-end
        preferredCuisines: [
          'fine dining',
          'steakhouse',
          'seafood',
          'french',
          'italian',
        ],
        avoidCuisines: ['fast food', 'cafe'],
        minRating: 4.2,
        atmosphereKeywords: ['upscale', 'elegant', 'special', 'celebration'],
      },
    };

    const factors = eventFactors[event as keyof typeof eventFactors];
    if (!factors) return 5; // Default score

    let score = 5; // Base score

    // Price level suitability
    if (
      restaurant.priceLevel &&
      factors.preferredPriceLevel.includes(restaurant.priceLevel)
    ) {
      score += 2;
    }

    // Cuisine suitability
    const restaurantCuisines = restaurant.cuisineTypes.map(c =>
      c.toLowerCase()
    );
    const hasPreferredCuisine = factors.preferredCuisines.some(cuisine =>
      restaurantCuisines.some(rc => rc.includes(cuisine))
    );
    const hasAvoidedCuisine = factors.avoidCuisines.some(cuisine =>
      restaurantCuisines.some(rc => rc.includes(cuisine))
    );

    if (hasPreferredCuisine) score += 2;
    if (hasAvoidedCuisine) score -= 3;

    // Rating suitability
    if (restaurant.rating >= factors.minRating) {
      score += 1;
    } else {
      score -= 2;
    }

    return Math.max(1, Math.min(10, score));
  }

  /**
   * Calculate mood match (1-10 scale)
   */
  private calculateMoodMatch(restaurant: Restaurant, mood: string): number {
    const moodKeywords = {
      romantic: ['intimate', 'cozy', 'candlelit', 'wine', 'date', 'romantic'],
      casual: ['casual', 'relaxed', 'friendly', 'laid-back', 'comfortable'],
      upscale: ['upscale', 'elegant', 'sophisticated', 'fine', 'luxury'],
      fun: ['lively', 'energetic', 'vibrant', 'entertainment', 'music'],
      quiet: ['quiet', 'peaceful', 'serene', 'calm', 'tranquil'],
      adventurous: ['unique', 'exotic', 'fusion', 'creative', 'innovative'],
      traditional: [
        'traditional',
        'authentic',
        'classic',
        'heritage',
        'original',
      ],
    };

    const keywords =
      moodKeywords[mood.toLowerCase() as keyof typeof moodKeywords] || [];
    if (keywords.length === 0) return 5; // Default score

    let score = 5; // Base score
    let matches = 0;

    // Check restaurant name, cuisine types, and reviews for mood keywords
    const searchText = [
      restaurant.name,
      ...restaurant.cuisineTypes,
      ...(restaurant.reviews?.map(r => r.text) || []),
    ]
      .join(' ')
      .toLowerCase();

    for (const keyword of keywords) {
      if (searchText.includes(keyword)) {
        matches++;
      }
    }

    // Adjust score based on matches
    if (matches > 0) {
      score += Math.min(matches * 1.5, 4); // Cap at +4
    }

    // Consider price level for certain moods
    if (restaurant.priceLevel) {
      if (mood.toLowerCase() === 'upscale' && restaurant.priceLevel >= 3) {
        score += 1;
      } else if (
        mood.toLowerCase() === 'casual' &&
        restaurant.priceLevel <= 2
      ) {
        score += 1;
      }
    }

    return Math.max(1, Math.min(10, score));
  }

  /**
   * Generate human-readable reasoning for the recommendation
   */
  private generateReasoning(
    restaurant: Restaurant,
    params: RestaurantSearchParams,
    score: number,
    eventSuitability: number,
    moodMatch: number
  ): string {
    const reasons: string[] = [];

    // Rating and reviews
    if (restaurant.rating >= 4.5) {
      reasons.push(
        `Excellent rating of ${restaurant.rating}/5 with ${restaurant.userRatingsTotal} reviews`
      );
    } else if (restaurant.rating >= 4.0) {
      reasons.push(
        `High rating of ${restaurant.rating}/5 with ${restaurant.userRatingsTotal} reviews`
      );
    } else if (restaurant.rating >= 3.5) {
      reasons.push(`Good rating of ${restaurant.rating}/5`);
    }

    // Cuisine match
    if (params.cuisineTypes.length > 0) {
      const matchingCuisines = restaurant.cuisineTypes.filter(rc =>
        params.cuisineTypes.some(
          sc =>
            rc.toLowerCase().includes(sc.toLowerCase()) ||
            sc.toLowerCase().includes(rc.toLowerCase())
        )
      );
      if (matchingCuisines.length > 0) {
        reasons.push(
          `Serves ${matchingCuisines.join(', ')} cuisine as requested`
        );
      }
    }

    // Event suitability
    if (eventSuitability >= 8) {
      reasons.push(`Perfect for ${params.event}`);
    } else if (eventSuitability >= 6) {
      reasons.push(`Well-suited for ${params.event}`);
    }

    // Mood match
    if (moodMatch >= 8) {
      reasons.push(`Excellent match for ${params.mood} mood`);
    } else if (moodMatch >= 6) {
      reasons.push(`Good fit for ${params.mood} atmosphere`);
    }

    // Price level
    if (restaurant.priceLevel) {
      const priceLabels = [
        '',
        'Budget-friendly',
        'Moderately priced',
        'Upscale',
        'High-end',
      ];
      reasons.push(priceLabels[restaurant.priceLevel]);
    }

    // Opening hours
    if (restaurant.openingHours?.openNow) {
      reasons.push('Currently open');
    }

    return reasons.length > 0
      ? reasons.join('. ') + '.'
      : 'Recommended based on location and general criteria.';
  }
}
