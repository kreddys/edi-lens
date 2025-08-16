#!/usr/bin/env python3
"""
Simple test for TA1 generation.
"""

def realistic_ta1_generation(edi_content: str) -> str:
    """Generate realistic TA1 acknowledgment."""
    
    # Extract ISA information
    lines = edi_content.split('\n')
    isa_line = next((line for line in lines if line.startswith('ISA*')), "")
    
    from datetime import datetime
    
    if not isa_line:
        # Generate fallback TA1
        current_time = datetime.utcnow()
        date_str = current_time.strftime('%y%m%d')
        time_str = current_time.strftime('%H%M')
        return f"ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *{date_str}*{time_str}*U*00401*000000001*0*P*>~TA1*000000001*{date_str}*{time_str}*A*000~IEA*1*000000001~"
    
    # Parse ISA elements
    isa_elements = isa_line.split('*')
    
    if len(isa_elements) >= 15:
        sender_id = isa_elements[6].strip()[:15].ljust(15)
        receiver_id = isa_elements[8].strip()[:15].ljust(15)
        control_number = isa_elements[13].strip()
        
        # Generate reciprocal TA1
        current_time = datetime.utcnow()
        date_str = current_time.strftime('%y%m%d')
        time_str = current_time.strftime('%H%M')
        
        ta1_response = (
            f"ISA*00*          *00*          *ZZ*{receiver_id}*ZZ*{sender_id}*"
            f"{date_str}*{time_str}*U*00401*{control_number.zfill(9)}*0*P*>~"
            f"TA1*{control_number}*{date_str}*{time_str}*A*000~"
            f"IEA*1*{control_number.zfill(9)}~"
        )
        
        return ta1_response
    
    # Fallback TA1
    return "ISA*00*          *00*          *ZZ*RECEIVER       *ZZ*SENDER         *250816*1031*U*00401*000000001*0*P*>~TA1*000000001*250816*1031*A*000~IEA*1*000000001~"

# Test the function
edi_content = "ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250816*1030*U*00401*000000001*0*P*>~IEA*1*000000001~"
result = realistic_ta1_generation(edi_content)
print('Result:', repr(result))
print('Contains *TA1*:', '*TA1*' in result)