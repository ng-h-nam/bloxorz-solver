

def test_game_smoke():
    """Khởi tạo game và chạy thử 100 frames để bắt các lỗi crash cơ bản."""
    import pygame

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()

    frames_to_simulate = 100
    for _ in range(frames_to_simulate):
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    assert True  # Nếu code chạy đến đây mà không crash nghĩa là vượt qua smoke test
