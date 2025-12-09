from ai_form_filler import ai_filler

# Test if Ollama is available
if ai_filler.is_ollama_available():
    print("✓ Ollama is ready!")
    
    # Run test cases
    ai_filler.test_generation()
else:
    print("✗ Ollama is not available")