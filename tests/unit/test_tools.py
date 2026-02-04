"""
Unit tests for Modal agent tools.

Tests individual tool components in isolation.
"""

import pytest

import sys
sys.path.insert(0, str(__file__).rsplit("/tests", 1)[0])

from modal_agent.tools import AskUserException


class TestAskUserExceptionUnit:
    """Unit tests for AskUserException."""

    def test_exception_is_exception_subclass(self):
        """AskUserException should be a proper Exception subclass."""
        assert issubclass(AskUserException, Exception)

    def test_exception_can_be_raised(self):
        """AskUserException should be raisable."""
        with pytest.raises(AskUserException):
            raise AskUserException(
                question="Test?",
                context="Test context",
            )

    def test_exception_preserves_attributes_after_catch(self):
        """Exception attributes should be accessible after catching."""
        try:
            raise AskUserException(
                question="What is X?",
                context="Need X for Y",
                options=["Option 1", "Option 2"],
            )
        except AskUserException as e:
            assert e.question == "What is X?"
            assert e.context == "Need X for Y"
            assert e.options == ["Option 1", "Option 2"]

    def test_exception_with_empty_question(self):
        """Exception should handle empty question string."""
        exc = AskUserException(question="", context="Some context")
        assert exc.question == ""

    def test_exception_with_long_context(self):
        """Exception should handle long context strings."""
        long_context = "A" * 10000
        exc = AskUserException(question="Q?", context=long_context)
        assert len(exc.context) == 10000

    def test_exception_with_many_options(self):
        """Exception should handle many options."""
        many_options = [f"Option {i}" for i in range(100)]
        exc = AskUserException(
            question="Choose one?",
            context="Many choices",
            options=many_options,
        )
        assert len(exc.options) == 100

    def test_exception_options_is_list(self):
        """Exception options should always be a list."""
        exc = AskUserException(question="Q?", context="C")
        assert isinstance(exc.options, list)

    def test_exception_str_representation(self):
        """Exception should have useful string representation."""
        exc = AskUserException(
            question="What color?",
            context="Need to choose a color",
        )
        exc_str = str(exc)
        assert "AskUser" in exc_str
        assert "What color?" in exc_str
