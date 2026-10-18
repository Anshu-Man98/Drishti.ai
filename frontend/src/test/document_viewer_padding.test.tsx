import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DocumentViewer } from '../components/DocumentViewer';

describe('DocumentViewer & ClaimDetail Padding and Layout Fix', () => {
  it('renders DocumentViewer container without h-full to avoid artificial vertical stretching', () => {
    const { container } = render(
      <MemoryRouter>
        <DocumentViewer
          claimId="CLM-TEST-001"
          pageCount={1}
          findings={[]}
          entities={[]}
        />
      </MemoryRouter>
    );

    // The root div of DocumentViewer
    const rootCard = container.firstChild as HTMLElement;
    expect(rootCard).toBeDefined();

    // Must NOT have h-full which stretched the viewer to match 2000px+ audit dossiers
    expect(rootCard.classList.contains('h-full')).toBe(false);

    // Should have standard padding and card styling
    expect(rootCard.classList.contains('p-5')).toBe(true);
    expect(rootCard.classList.contains('flex')).toBe(true);
    expect(rootCard.classList.contains('flex-col')).toBe(true);
  });
});
