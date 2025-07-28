import { expect, it, Test } from 'azle/_internal/test';

export function getTests(canisterId: string): Test {
    const origin = `http://${canisterId}.raw.localhost:4943`;

    return () => {
        it('gets a simple hello world database', async () => {
            const response = await fetch(`${origin}/db`);
            const responseJson = await response.json();

            expect(responseJson).toEqual({ hello: '' });
        });

        it('updates a simple hello world database', async () => {
            const response = await fetch(`${origin}/db/update`, {
                method: 'POST',
                headers: [['Content-Type', 'application/json']],
                body: JSON.stringify({
                    hello: 'world'
                })
            });
            const responseJson = await response.json();

            expect(responseJson).toEqual({ hello: 'world' });
        });
    };
}
