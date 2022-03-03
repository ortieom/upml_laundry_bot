class ReplyKeyboard:
    """
    собрал частоиспользуемые клавиатуры в один класс
    """
    drying_time = [[['12', '15'], ['отменить']],
                   [[{'color': 'secondary'} for _ in range(2)], [{'color': 'secondary'}]]]
    washing_time = [[['40', '70'], ['отменить']],
                    [[{'color': 'secondary'} for _ in range(2)], [{'color': 'secondary'}]]]
    interval_dried = [[['1', '1 30', '2', '3'], ['отменить']],
                      [[{'color': 'secondary'} for _ in range(4)], [{'color': 'secondary'}]]]
    interval_washed = [[['30', '45', '60', '90'], ['отменить']],
                       [[{'color': 'secondary'} for _ in range(4)], [{'color': 'secondary'}]]]
    cancel = [[['отменить']], [[{'color': 'secondary'}]]]

    main_settings_inline = [[["интервалы", "время тишины"]], [[{'color': 'secondary'} for _ in range(2)]], True]
    intervals_inline = [[["/set_washing_time"], ["/set_interval_washed"],
                         ["/set_drying_time"], ["/set_interval_dried"]],
                        [[{'color': 'secondary'}] for _ in range(4)], True]
    inactive_time_inline = [[["/list_inactive_time"], ["/add_inactive_time"], ["/delete_inactive_time"]],
                            [[{'color': 'secondary'}] for _ in range(3)], True]
