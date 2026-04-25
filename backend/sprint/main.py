from backend.shared.ai import get_ai_service, validate_settings


def main():
    validate_settings()
    get_ai_service()
    print("Sprint AI stack setup is ready.")


if __name__ == "__main__":
    main()
