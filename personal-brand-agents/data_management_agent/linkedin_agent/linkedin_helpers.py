from shared_clients.composio_client import composio

LINKEDIN_AUTH_CONFIG_ID = "ac_S29IN2PEi_IR"
def get_linkedin_auth_url(asi_one_id: str):
    connection_request = composio.connected_accounts.link(asi_one_id, LINKEDIN_AUTH_CONFIG_ID)

    redirect_url = connection_request.redirect_url
    return redirect_url

def get_linkedin_urn(asi_one_id: str) -> str | None:
    # LinkedIn post tool
    tool_slug = "LINKEDIN_GET_MY_INFO"
    input_payload = {}

    try:
        # Call the LinkedIn post tool
        response = composio.tools.execute(
            slug=tool_slug,
            arguments=input_payload,
            user_id=asi_one_id
        )
        urn = response["data"]["response_dict"]["author_id"]
        return urn

    except Exception as e:
        print(f"Error fetching LinkedIn URN: {e}")
        # Either the user isn't linked, or LinkedIn didn't return expected data
        return None

    
if __name__ == "__main__":
    asi_one_id = "agent1q29tg4sgdzg33gr7u63hfemq4hk54thsya3s7kygurrxg3j8p8f2qlnxz9f"
    auth_url = get_linkedin_auth_url(asi_one_id)
    print(auth_url)