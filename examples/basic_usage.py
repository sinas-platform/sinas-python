"""Basic usage example for SINAS Runtime SDK."""

import os
import json
from sinas import SinasClient

# Initialize client
# You can set SINAS_BASE_URL and SINAS_API_KEY environment variables
# or pass them directly to the client
client = SinasClient(
    base_url=os.getenv("SINAS_BASE_URL", "http://localhost:51245"),
    api_key=os.getenv("SINAS_API_KEY"),
)


def main():
    """Demonstrate basic Runtime API usage."""
    try:
        # Get current user info
        user = client.auth.get_me()
        print(f"Logged in as: {user['email']}")

        # === State Management ===
        print("\n=== State Management ===")

        # Set a state value
        state = client.state.set(
            namespace="user_prefs",
            key="theme",
            value={"mode": "dark", "accent": "blue"},
            description="User theme preferences"
        )
        print(f"Created state: {state['id']}")

        # Get the state
        retrieved_state = client.state.get(state['id'])
        print(f"Retrieved state value: {retrieved_state['value']}")

        # List states
        states = client.state.list(namespace="user_prefs")
        print(f"Found {len(states)} states in 'user_prefs' namespace")

        # Update state
        updated_state = client.state.update(
            state['id'],
            value={"mode": "light", "accent": "green"}
        )
        print(f"Updated state value: {updated_state['value']}")

        # Delete state
        client.state.delete(state['id'])
        print(f"Deleted state: {state['id']}")

        # === Chat with Agent ===
        print("\n=== Chat with Agent ===")

        # Create a chat with an agent
        chat = client.chats.create(
            namespace="customer-support",
            agent_name="cs-agent-v1",
            title="SDK Test Chat"
        )
        print(f"Created chat: {chat['id']}")

        # Send a message (blocking)
        print("\nSending message...")
        response = client.chats.send(
            chat_id=chat["id"],
            content="Hello! Can you help me test this SDK?"
        )
        print(f"Assistant: {response.get('content', response)}")

        # Stream a message
        print("\nStreaming message...")
        print("Assistant: ", end="", flush=True)
        for chunk in client.chats.stream(
            chat_id=chat["id"],
            content="Tell me a short joke"
        ):
            # Parse SSE data
            try:
                data = json.loads(chunk)
                if "content" in data:
                    print(data["content"], end="", flush=True)
            except:
                pass
        print("\n")

        # Get chat with messages
        chat_with_messages = client.chats.get(chat["id"])
        print(f"Chat has {len(chat_with_messages.get('messages', []))} messages")

        # Clean up
        client.chats.delete(chat["id"])
        print(f"Deleted chat: {chat['id']}")

        # === Webhook Execution ===
        print("\n=== Webhook Execution ===")

        # Execute a webhook (if you have one configured)
        # result = client.webhooks.run(
        #     path="process-payment",
        #     method="POST",
        #     body={"amount": 100, "currency": "USD"}
        # )
        # print(f"Webhook result: {result}")

        # === Executions ===
        print("\n=== Executions ===")

        # List recent executions
        executions = client.executions.list(limit=5)
        print(f"Found {len(executions)} recent executions")

        if executions:
            execution = executions[0]
            print(f"Latest execution: {execution.get('execution_id')} - Status: {execution.get('status')}")

            # Get execution details
            details = client.executions.get(execution['execution_id'])
            print(f"Execution function: {details.get('function_name')}")

            # Get execution steps
            steps = client.executions.get_steps(execution['execution_id'])
            print(f"Execution has {len(steps)} steps")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
