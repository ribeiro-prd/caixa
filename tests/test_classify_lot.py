from caixa_joias.core.classify_lot import classify_lot

def test_classify_coin_986():
    row = classify_lot('UMA MOEDA DE 01 DUCADO, AUSTRIA, 1915, OURO 986')
    assert row['tipo_lote'] == 'moeda'
    assert row['teor_detectado'] == 0.986
    assert row['contem_moeda'] is True
