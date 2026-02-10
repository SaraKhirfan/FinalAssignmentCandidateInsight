import os
from openai import OpenAI
import pdfplumber
import json
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
import re

class ResumeParser:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        
        # Configure Tesseract path (Windows)
        if os.name == 'nt':  # Windows
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    def extract_text_from_pdf(self, pdf_path):
        """Extract text from PDF using pdfplumber, fallback to OCR"""
        try:
            print(f"   📖 Trying text extraction with pdfplumber...")
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            
            text = text.strip()
            
            if len(text) > 100:
                print(f"   ✅ Text extraction successful ({len(text)} chars)")
                return text
            else:
                print(f"   ⚠️  Minimal text found ({len(text)} chars), attempting OCR...")
                return self.extract_text_with_ocr(pdf_path)
                
        except Exception as e:
            print(f"   ❌ Text extraction error: {e}")
            print(f"   🔄 Falling back to OCR...")
            return self.extract_text_with_ocr(pdf_path)
    
    def extract_text_with_ocr(self, pdf_path):
        """Extract text from PDF using OCR (for scanned documents)"""
        try:
            print(f"   🔍 Starting OCR process...")
            images = convert_from_path(pdf_path, dpi=300)
            print(f"   📄 Converted to {len(images)} image(s)")
            
            text = ""
            for i, image in enumerate(images):
                print(f"   🔍 OCR processing page {i+1}/{len(images)}...")
                page_text = pytesseract.image_to_string(image, lang='eng+ara')
                text += page_text + "\n"
            
            text = text.strip()
            
            if len(text) > 50:
                print(f"   ✅ OCR successful ({len(text)} chars extracted)")
                return text
            else:
                print(f"   ❌ OCR failed - minimal text extracted")
                return None
                
        except Exception as e:
            print(f"   ❌ OCR error: {e}")
            print(f"   💡 Make sure Tesseract is installed and poppler is in PATH")
            return None
    
    def extract_text_from_txt(self, txt_path):
        """Extract text from TXT file"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as file:
                text = file.read()
            return text.strip()
        except Exception as e:
            print(f"Error extracting TXT: {e}")
            return None
    
    def normalize_arabic_text(self, text):
        """
        Normalize Arabic text by removing diacritics and extra whitespace.
        This helps with keyword matching.
        """
        if not text:
            return ""
        
        # Remove Arabic diacritics (tashkeel)
        arabic_diacritics = re.compile(r'[\u064B-\u065F\u0670]')
        text = arabic_diacritics.sub('', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text
    
    def is_valid_resume(self, resume_text):
        """
        Validate if the extracted text is actually a resume/CV
        Returns: (is_valid: bool, reason: str)
        """
        if not resume_text or len(resume_text.strip()) < 100:
            return False, "Document too short (less than 100 characters)"
        
        text_lower = resume_text.lower()
        
        # Normalize Arabic text for better matching
        normalized_text = self.normalize_arabic_text(resume_text)
        
        # Define CV-related keywords (comprehensive list)
        cv_keywords_english = {
            # Section headers
            'experience', 'education', 'skills', 'work experience', 'employment',
            'qualifications', 'profile', 'summary', 'objective', 'career',
            'professional experience', 'work history', 'academic background',
            'certifications', 'certificates', 'training', 'projects',
            'achievements', 'accomplishments', 'references',
            
            # Contact-related
            'email', 'phone', 'mobile', 'address', 'linkedin', 'portfolio',
            'contact', 'tel', 'website', 'gmail', 'hotmail', 'yahoo',
            
            # Common resume phrases
            'years of experience', 'worked at', 'worked as', 'responsible for',
            'degree in', 'bachelor', 'master', 'diploma', 'graduated',
            'university', 'college', 'institute', 'resume', 'curriculum vitae',
            'cv', 'personal information', 'developer', 'engineer', 'manager',
            'analyst', 'designer', 'specialist', 'coordinator'
        }
        
        # Arabic keywords (normalized - without diacritics and flexible spacing)
        cv_keywords_arabic = [
            # Core sections (most common variations)
            'خبرة', 'خبرات', 'الخبرة', 'الخبرات',
            'تعليم', 'التعليم', 'مؤهل', 'مؤهلات', 'المؤهل', 'المؤهلات',
            'مهارة', 'مهارات', 'المهارات', 'المهارة',
            'شهادة', 'شهادات', 'الشهادات',
            'دورة', 'دورات', 'الدورات',
            'مشروع', 'مشاريع', 'المشاريع',
            'انجاز', 'انجازات', 'الانجازات',
            
            # Education terms
            'بكالوريوس', 'ماجستير', 'دبلوم', 'دكتوراه',
            'جامعة', 'الجامعة', 'كلية', 'الكلية', 'معهد', 'المعهد',
            'تخرج', 'التخرج',
            
            # Experience terms
            'عمل', 'العمل', 'وظيفة', 'الوظيفة',
            'شركة', 'الشركة', 'مؤسسة', 'المؤسسة',
            'مطور', 'مهندس', 'محلل', 'مصمم', 'مدير',
            'مطورة', 'مهندسة', 'محللة', 'مصممة', 'مديرة',
            
            # Contact/Personal
            'اسم', 'الاسم', 'هاتف', 'الهاتف', 'جوال', 'الجوال',
            'بريد', 'البريد', 'الكتروني', 'موقع', 'الموقع',
            'عنوان', 'العنوان', 'جنسية', 'الجنسية',
            
            # Other common CV terms
            'سيرة', 'السيرة', 'ذاتية', 'الذاتية',
            'معلومات', 'شخصية', 'ملخص', 'الملخص',
            'مهني', 'المهني', 'تقني', 'التقني',
            'لغات', 'اللغات', 'لغة'
        ]
        
        # Count English keywords (case-insensitive)
        english_count = sum(1 for keyword in cv_keywords_english if keyword in text_lower)
        
        # Count Arabic keywords with normalization
        arabic_count = 0
        matched_arabic = []
        for keyword in cv_keywords_arabic:
            normalized_keyword = self.normalize_arabic_text(keyword)
            if normalized_keyword in normalized_text:
                arabic_count += 1
                matched_arabic.append(keyword)
        
        total_keywords = english_count + arabic_count
        
        # Debug: Show which Arabic keywords were found
        if arabic_count > 0:
            print(f"   🔍 Arabic keywords found: {', '.join(matched_arabic[:5])}{'...' if len(matched_arabic) > 5 else ''}")
        
        print(f"   🔍 CV validation: Found {english_count} English + {arabic_count} Arabic = {total_keywords} total CV keywords")
        
        # Check for Arabic content
        has_arabic = bool(re.search(r'[\u0600-\u06FF]', resume_text))
        if has_arabic:
            print(f"   📝 Document contains Arabic text")
        
        # Threshold: At least 3 CV-related keywords should be present
        if total_keywords >= 3:
            if arabic_count > 0:
                return True, f"Valid Arabic CV detected ({arabic_count} Arabic keywords, {english_count} English keywords)"
            else:
                return True, f"Valid CV detected ({total_keywords} keywords found)"
        else:
            # If document has Arabic but low keyword count, might be formatting issue
            if has_arabic and arabic_count > 0:
                print(f"   ⚠️  Arabic CV detected but low keyword count - accepting anyway")
                return True, f"Arabic CV detected with {arabic_count} keywords (accepted with warning)"
            
            return False, f"Does not appear to be a CV (only {total_keywords} CV keywords found). Please upload a document with sections like Skills, Experience, Education."
    
    def parse_resume(self, resume_text, output_language='en'):
        """
        Use OpenAI to parse resume with validation and anti-hallucination
        
        Args:
            resume_text (str): The extracted resume text
            output_language (str): 'en' for English output, 'ar' for Arabic output
        """
        
        if not resume_text or len(resume_text.strip()) < 50:
            print("   ❌ Resume text too short or empty")
            return None
        
        # VALIDATE: Check if this is actually a CV/resume
        is_valid, validation_reason = self.is_valid_resume(resume_text)
        
        if not is_valid:
            print(f"   ❌ VALIDATION FAILED: {validation_reason}")
            return {
                'error': 'NOT_A_CV',
                'message': validation_reason,
                'is_valid_cv': False
            }
        
        print(f"   ✅ VALIDATION PASSED: {validation_reason}")
        print(f"   🌐 Output language: {'Arabic' if output_language == 'ar' else 'English'}")
        
        # BILINGUAL PROMPTS
        if output_language == 'ar':
            # ARABIC OUTPUT
            prompt = f"""
أنت خبير في تحليل السير الذاتية مع قدرات متعددة اللغات.

تعليمات حاسمة - لغة الإخراج:
- السيرة الذاتية قد تكون بالإنجليزية، العربية، أو أي لغة أخرى
- يجب أن تعيد جميع المعلومات المستخرجة بالعربية
- إذا كان اسم المرشح بالإنجليزية (مثل John Smith)، احتفظ به كما هو
- إذا كان اسم المرشح بالعربية (مثل أحمد محمد)، احتفظ به بالعربية
- ترجم جميع المهارات التقنية، المسميات الوظيفية، والشركات إلى العربية حيثما أمكن
- المهارات التقنية التي ليس لها ترجمة عربية شائعة (مثل Flutter, Python) اتركها بالإنجليزية

قواعد مكافحة التهيؤات - حاسمة:
1. استخرج فقط المعلومات المذكورة صراحةً في نص السيرة الذاتية
2. إذا لم يتم ذكر حقل ما، اتركه فارغاً أو استخدم مصفوفة فارغة []
3. لا تستنتج، لا تفترض، ولا تولد معلومات غير موجودة
4. لا تضف مهارات عامة لم تُذكر
5. إذا كنت غير متأكد من حقل ما، أضف درجة ثقة (0-100)

عملية خطوة بخطوة:
الخطوة 1: اقرأ السيرة الذاتية بالكامل بعناية
الخطوة 2: حدد الأقسام الواضحة (معلومات التواصل، المهارات، الخبرة، التعليم)
الخطوة 3: استخرج فقط المعلومات المذكورة صراحةً
الخطوة 4: ترجم إلى العربية (احتفظ بالأسماء والمصطلحات التقنية كما هي)
الخطوة 5: تحقق من كل حقل مستخرج مقابل النص المصدر
الخطوة 6: أضف درجات الثقة

استخرج المعلومات التالية وأعدها بصيغة JSON:

{{
    "الاسم": "الاسم الكامل للمرشح - فقط إذا كان مذكوراً بوضوح",
    "البريد_الالكتروني": "عنوان البريد الإلكتروني - فقط إذا كان موجوداً",
    "الهاتف": "رقم الهاتف - فقط إذا كان موجوداً",
    "المهارات": ["قائمة المهارات التقنية والشخصية - فقط المهارات المذكورة صراحةً"],
    "الخبرة": "ملخص الخبرة العملية بالعربية - فقط إذا ذُكرت",
    "التعليم": "المؤهلات التعليمية بالعربية - فقط إذا ذُكرت",
    "الملخص": "ملخص مهني مختصر بالعربية (2-3 جمل) - بناءً على المحتوى الفعلي",
    "الثقة": {{
        "الاسم": <0-100>,
        "البريد_الالكتروني": <0-100>,
        "الهاتف": <0-100>,
        "المهارات": <0-100>,
        "الخبرة": <0-100>,
        "التعليم": <0-100>
    }}
}}

تقييم درجة الثقة:
- 100: الحقل مذكور بوضوح وصراحة
- 80-99: الحقل موجود ولكن قد يحتاج إلى تفسير بسيط
- 60-79: الحقل موجود جزئياً أو يتطلب ترجمة
- 40-59: الحقل مستنتج من السياق (استخدم بحذر)
- 0-39: الحقل غير مؤكد أو مفقود (اتركه فارغاً)

أمثلة على الترجمة:
- "Software Engineer" → "مهندس برمجيات"
- "Python" → "Python" (اترك كما هي)
- "University of Jordan" → "الجامعة الأردنية"
- "Mobile App Developer" → "مطور تطبيقات موبايل"

حاسم: قد يكون النص من OCR وقد يحتوي على أخطاء. كن مرناً ولكن لا تتخيل معلومات.
إذا لم تتمكن من إيجاد حقل بثقة > 60، اتركه فارغاً.

نص السيرة الذاتية:
{resume_text}

أعد فقط JSON صحيح بالعربية، بدون نص إضافي أو تنسيق markdown.
"""
            system_content = "أنت محلل سير ذاتية محترف متعدد اللغات. لا تتخيل أو تخترع معلومات أبداً. يمكنك قراءة السير الذاتية بأي لغة ولكن أعد دائماً JSON صحيح بالعربية فقط. ترجم المحتوى إلى العربية مع الاحتفاظ بالأسماء والمصطلحات التقنية. لا تضمن كتل أكواد markdown أو أي تنسيق آخر. كن متسامحاً مع أخطاء OCR ولكن استخرج فقط المعلومات الموجودة فعلياً في النص المصدر. عندما تكون غير متأكد، استخدم درجات ثقة منخفضة."
        
        else:
            # ENGLISH OUTPUT (Original)
            prompt = f"""
You are an expert resume parser with multilingual capabilities.

CRITICAL INSTRUCTION - OUTPUT LANGUAGE:
- The resume may be in English, Arabic, or any other language
- You MUST return ALL extracted information in ENGLISH
- If the candidate's name is in Arabic (e.g., أحمد محمد), transliterate it to English (e.g., Ahmed Mohammed)
- Translate all skills, job titles, companies, and education to English
- Preserve the original meaning while converting to English

ANTI-HALLUCINATION RULES - CRITICAL:
1. ONLY extract information that is EXPLICITLY stated in the resume text
2. If a field is not mentioned, leave it empty or use empty array []
3. DO NOT infer, assume, or generate information not present
4. DO NOT add generic skills that aren't mentioned
5. If uncertain about a field, include a confidence score (0-100)

STEP-BY-STEP PROCESS:
Step 1: Read the entire resume carefully
Step 2: Identify clear sections (contact, skills, experience, education)
Step 3: Extract ONLY explicitly mentioned information
Step 4: Translate/transliterate to English
Step 5: Verify each extracted field against source text
Step 6: Assign confidence scores

Extract the following information and return it in JSON format:

{{
    "name": "candidate's full name (in English/transliterated) - ONLY if clearly stated",
    "email": "email address - ONLY if present",
    "phone": "phone number - ONLY if present",
    "skills": ["list of technical and soft skills in English - ONLY skills explicitly mentioned"],
    "experience": "work experience summary in English - ONLY if mentioned",
    "education": "educational qualifications in English - ONLY if mentioned",
    "summary": "brief professional summary in English (2-3 sentences) - based on actual content",
    "confidence": {{
        "name": <0-100>,
        "email": <0-100>,
        "phone": <0-100>,
        "skills": <0-100>,
        "experience": <0-100>,
        "education": <0-100>
    }}
}}

CONFIDENCE SCORING:
- 100: Field is clearly and explicitly stated
- 80-99: Field is present but may need minor interpretation
- 60-79: Field is partially present or requires translation
- 40-59: Field is inferred from context (use cautiously)
- 0-39: Field is uncertain or missing (leave empty)

Examples of translation/transliteration:
- "مهندس برمجيات" → "Software Engineer"
- "بايثون" → "Python"
- "الجامعة الأردنية" → "University of Jordan"
- "محمد أحمد" → "Mohammed Ahmed"
- "آية خالد" → "Aya Khaled"
- "مطورة تطبيقات موبايل" → "Mobile Application Developer"

CRITICAL: The text may come from OCR and might have errors. Be flexible but DO NOT hallucinate.
If you cannot find a field with confidence >60, leave it empty.

Resume text:
{resume_text}

Return ONLY valid JSON in English, no additional text or markdown formatting.
"""
            system_content = "You are a professional multilingual resume parser. You NEVER hallucinate or invent information. You can read resumes in any language but ALWAYS respond with valid JSON in ENGLISH only. Transliterate names and translate all content to English. Do not include markdown code blocks or any other formatting. Be tolerant of OCR errors but ONLY extract information that is actually present in the source text. When uncertain, use low confidence scores."
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith('```'):
                response_text = response_text.split('```')[1]
                if response_text.startswith('json'):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            parsed_data = json.loads(response_text)
            
            # Add validation flag and language
            parsed_data['is_valid_cv'] = True
            parsed_data['output_language'] = output_language
            
            # Quality validation
            confidence_key = 'الثقة' if output_language == 'ar' else 'confidence'
            if parsed_data.get(confidence_key):
                avg_confidence = sum(parsed_data[confidence_key].values()) / len(parsed_data[confidence_key])
                print(f"   📊 Average confidence: {avg_confidence:.1f}%")
                
                if avg_confidence < 70:
                    print(f"   ⚠️  Low confidence extraction - resume may be unclear or OCR quality poor")
            
            # Check for Arabic characters in name (for English mode)
            if output_language == 'en' and parsed_data.get('name'):
                if any('\u0600' <= char <= '\u06FF' for char in str(parsed_data.get('name', ''))):
                    print("   ⚠️  Warning: Name still contains Arabic characters (transliteration incomplete)")
            
            return parsed_data
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing error: {e}")
            print(f"   📄 Response was: {response_text[:200]}...")
            return None
        except Exception as e:
            print(f"   ❌ Error parsing resume: {e}")
            return None