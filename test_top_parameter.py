"""
Script de prueba para verificar la funcionalidad del parámetro top
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from lib.config_store import PDFOrientationConfigStore
from lib.pdf import generate

def test_top_parameter():
    """Prueba la funcionalidad del parámetro top"""
    print("=== Prueba del parámetro TOP ===")
    
    # Inicializar el config store
    config_store = PDFOrientationConfigStore()
    
    # Cargar configuraciones actuales
    landscape_config = config_store.get_orientation_config('landscape')
    portrait_config = config_store.get_orientation_config('portrait')
    
    print(f"Configuración landscape cargada: {landscape_config}")
    print(f"Configuración portrait cargada: {portrait_config}")
    
    print(f"Configuración landscape: {landscape_config}")
    print(f"Configuración portrait: {portrait_config}")
    
    # Verificar que el parámetro top está presente
    assert 'top' in landscape_config, "El parámetro 'top' no está en la configuración landscape"
    assert 'top' in portrait_config, "El parámetro 'top' no está en la configuración portrait"
    
    print("✓ El parámetro 'top' está presente en ambas configuraciones")
    
    # Probar con diferentes valores de top
    test_values = ['-60px', '0px', '20px', '-100px']
    
    for top_value in test_values:
        print(f"\n--- Probando con top: {top_value} ---")
        
        # Modificar la configuración landscape
        test_config = landscape_config.copy()
        test_config['top'] = top_value
        
        # Datos de prueba
        test_data = "Prueba de impresión con top: " + top_value
        
        try:
            # Generar PDF con el parámetro top
            pdf_content = generate(test_data, 'landscape', test_config)
            
            # Verificar que el PDF se generó
            if pdf_content and len(pdf_content) > 0:
                print(f"✓ PDF generado exitosamente con top: {top_value}")
                print(f"  Tamaño del PDF: {len(pdf_content)} bytes")
                
                # Guardar PDF de prueba
                filename = f"test_top_{top_value.replace('-', 'neg_').replace('px', '')}.pdf"
                with open(filename, 'wb') as f:
                    f.write(pdf_content)
                print(f"  PDF guardado como: {filename}")
            else:
                print(f"✗ Error: No se pudo generar PDF con top: {top_value}")
                
        except Exception as e:
            print(f"✗ Error generando PDF con top {top_value}: {str(e)}")
    
    print("\n=== Prueba completada ===")

if __name__ == "__main__":
    test_top_parameter()