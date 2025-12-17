"""Chat session management with history tracking."""

from typing import List, Optional, Dict, Any
from datetime import datetime

from providers.base import Message, CompletionResponse
from .router import ChatRouter


class ChatSession:
    """Manages a conversation session with history."""

    def __init__(
        self,
        conversation_id: str,
        router: ChatRouter,
        memory_store: Optional[Any] = None,
    ):
        """Initialize chat session.

        Args:
            conversation_id: Unique conversation identifier
            router: ChatRouter for sending messages
            memory_store: Optional memory store for persistence
        """
        self.conversation_id = conversation_id
        self.router = router
        self.memory_store = memory_store
        self.messages: List[Message] = []
        self.total_cost = 0.0
        self.total_tokens = 0

    async def send_message(
        self,
        content: str,
        role: str = "user",
        model: str = "auto",
        temperature: float = 1.0,
        **kwargs
    ) -> CompletionResponse:
        """Send a message and get response.

        Args:
            content: Message content
            role: Message role (user, assistant, system)
            model: Model to use or "auto"
            temperature: Sampling temperature
            **kwargs: Additional parameters

        Returns:
            CompletionResponse from the model
        """
        # Add user message to history
        user_message = Message(role=role, content=content)
        self.messages.append(user_message)

        # Get response from router
        response = await self.router.chat(
            messages=self.messages,
            model=model,
            temperature=temperature,
            **kwargs
        )

        # Add assistant response to history
        assistant_message = Message(
            role="assistant",
            content=response.content,
            metadata={
                "model": response.model,
                "provider": response.provider,
                "cost": response.cost,
                "tokens": response.usage.get("total_tokens", 0),
                "latency": response.latency,
            }
        )
        self.messages.append(assistant_message)

        # Update session statistics
        self.total_cost += response.cost
        self.total_tokens += response.usage.get("total_tokens", 0)

        # Save to memory store if available
        if self.memory_store:
            await self._save_to_memory(user_message, assistant_message, response)

        return response

    async def get_history(self, limit: int = 50) -> List[Message]:
        """Get conversation history.

        Args:
            limit: Maximum number of messages to return

        Returns:
            List of Message objects
        """
        if self.memory_store:
            # Try to load from memory store
            try:
                history = await self.memory_store.get_messages(
                    self.conversation_id, limit=limit
                )
                return history
            except Exception:
                # Fall back to in-memory history
                pass

        return self.messages[-limit:]

    async def stream_response(
        self,
        content: str,
        role: str = "user",
        model: str = "auto",
        temperature: float = 1.0,
        **kwargs
    ):
        """Stream a response (placeholder for future implementation).

        Args:
            content: Message content
            role: Message role
            model: Model to use
            temperature: Sampling temperature
            **kwargs: Additional parameters
        """
        # This would integrate with StreamHandler for SSE streaming
        # For now, fall back to regular send_message
        return await self.send_message(
            content=content,
            role=role,
            model=model,
            temperature=temperature,
            **kwargs
        )

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary for this session.

        Returns:
            Dictionary with cost statistics
        """
        return {
            "conversation_id": self.conversation_id,
            "total_cost": round(self.total_cost, 4),
            "total_tokens": self.total_tokens,
            "message_count": len(self.messages),
            "average_cost_per_message": round(
                self.total_cost / max(len(self.messages), 1), 4
            ),
        }

    async def _save_to_memory(
        self,
        user_message: Message,
        assistant_message: Message,
        response: CompletionResponse,
    ) -> None:
        """Save messages to memory store.

        Args:
            user_message: User's message
            assistant_message: Assistant's response
            response: Full completion response
        """
        try:
            await self.memory_store.add_message(
                conversation_id=self.conversation_id,
                message_data={
                    "user_message": {
                        "role": user_message.role,
                        "content": user_message.content,
                        "timestamp": datetime.now().isoformat(),
                    },
                    "assistant_message": {
                        "role": assistant_message.role,
                        "content": assistant_message.content,
                        "model": response.model,
                        "provider": response.provider,
                        "cost": response.cost,
                        "tokens": response.usage,
                        "latency": response.latency,
                        "timestamp": response.timestamp.isoformat(),
                    },
                },
            )
        except Exception as e:
            # Log but don't fail on memory store errors
            print(f"Failed to save to memory store: {e}")

    async def clear_history(self) -> None:
        """Clear conversation history."""
        self.messages = []
        self.total_cost = 0.0
        self.total_tokens = 0
