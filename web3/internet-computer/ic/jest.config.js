/** @type {import('ts-jest').JestConfigWithTsJest} */
module.exports = {
    preset: 'ts-jest',
    testEnvironment: 'node',
    testTimeout: 100_000_000,
    transform: {
        '^.+\\.ts$': [
            'ts-jest',
            {
                isolatedModules: true,
                astTransformers: {
                    before: [{ path: 'ts-jest-mock-import-meta' }]
                }
            }
        ],
        '^.+\\.js$': 'ts-jest'
    },
    transformIgnorePatterns: ['/node_modules/(?!(azle)/)'] // Make sure azle is transformed
};
