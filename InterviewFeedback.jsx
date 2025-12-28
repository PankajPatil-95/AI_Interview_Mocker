import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

/**
 * InterviewFeedback Component
 * 
 * Displays interview feedback with accordion-style question breakdown.
 * 
 * Props:
 * {
 *   overallScore: number (0-100),
 *   gradeLabel: string,
 *   summary: string,
 *   questions: [
 *     {
 *       id: string,
 *       question: string,
 *       score: number,
 *       answer: string,
 *       feedback: string,
 *       correctAnswer?: string
 *     }
 *   ],
 *   strengths?: string[],
 *   weaknesses?: string[],
 *   suggestions?: string[]
 * }
 */
const InterviewFeedback = ({
  overallScore = 75,
  gradeLabel = 'Good',
  summary = 'Great performance overall!',
  questions = [],
  strengths = [],
  weaknesses = [],
  suggestions = []
}) => {
  const [expandedId, setExpandedId] = useState(null);

  const toggleAccordion = (id) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        
        {/* Header Section */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-green-600 mb-3">
            Congratulations!
          </h1>
          <p className="text-xl text-gray-600 font-medium">
            Here is your interview feedback
          </p>
        </div>

        {/* Overall Rating Card */}
        <div className="bg-white rounded-2xl shadow-md p-10 mb-8 border-t-4 border-blue-500 text-center">
          <p className="text-gray-600 text-sm font-semibold uppercase tracking-widest mb-2">
            Your overall interview rating
          </p>
          <div className="flex items-center justify-center gap-1 mb-4">
            <span className="text-6xl font-bold text-blue-600">{overallScore}</span>
            <span className="text-3xl text-gray-400 font-light">/100</span>
          </div>
          <p className="text-xl font-semibold text-gray-700">
            {gradeLabel}
          </p>
          {summary && (
            <p className="text-gray-600 mt-4 leading-relaxed">
              {summary}
            </p>
          )}
        </div>

        {/* Summary Section */}
        {summary && (
          <div className="bg-white rounded-xl shadow-md p-6 mb-6">
            <h3 className="text-lg font-bold text-gray-800 mb-3">
              Interview Summary
            </h3>
            <p className="text-gray-700 leading-relaxed">
              {summary}
            </p>
          </div>
        )}

        {/* Strengths and Weaknesses Grid */}
        {(strengths.length > 0 || weaknesses.length > 0) && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            {/* Strengths */}
            {strengths.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6 border-l-4 border-green-500">
                <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
                  <span className="text-green-500 mr-2">✓</span>
                  Strengths
                </h3>
                <ul className="space-y-3">
                  {strengths.map((strength, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-green-500 mr-3 mt-1 flex-shrink-0">•</span>
                      <span className="text-gray-700">{strength}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Weaknesses */}
            {weaknesses.length > 0 && (
              <div className="bg-white rounded-xl shadow-md p-6 border-l-4 border-red-500">
                <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
                  <span className="text-red-500 mr-2">!</span>
                  Areas for Improvement
                </h3>
                <ul className="space-y-3">
                  {weaknesses.map((weakness, idx) => (
                    <li key={idx} className="flex items-start">
                      <span className="text-red-500 mr-3 mt-1 flex-shrink-0">•</span>
                      <span className="text-gray-700">{weakness}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Suggestions Section */}
        {suggestions.length > 0 && (
          <div className="bg-blue-50 rounded-xl shadow-md p-6 mb-8 border-l-4 border-blue-500">
            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center">
              <span className="text-blue-500 mr-2">→</span>
              Suggestions for Improvement
            </h3>
            <ul className="space-y-3">
              {suggestions.map((suggestion, idx) => (
                <li key={idx} className="flex items-start">
                  <span className="text-blue-500 mr-3 mt-1 flex-shrink-0">•</span>
                  <span className="text-gray-700">{suggestion}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Questions Accordion Section */}
        {questions.length > 0 && (
          <div className="mb-12">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">
              Question-by-Question Feedback
            </h2>
            <div className="space-y-4">
              {questions.map((q, idx) => (
                <div
                  key={q.id || idx}
                  className="bg-white rounded-xl shadow-md overflow-hidden transition-all duration-300"
                >
                  {/* Accordion Header */}
                  <button
                    onClick={() => toggleAccordion(q.id || idx)}
                    className="w-full px-6 py-5 flex items-center justify-between hover:bg-gray-50 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset"
                  >
                    <div className="text-left flex-1">
                      <p className="text-sm font-semibold text-blue-600 mb-2 uppercase tracking-wide">
                        Question {idx + 1}
                      </p>
                      <p className="text-gray-800 font-medium leading-relaxed">
                        {q.question}
                      </p>
                    </div>
                    <div className="ml-4 flex-shrink-0">
                      {expandedId === (q.id || idx) ? (
                        <ChevronUp className="w-6 h-6 text-gray-600 transition-transform" />
                      ) : (
                        <ChevronDown className="w-6 h-6 text-gray-600 transition-transform" />
                      )}
                    </div>
                  </button>

                  {/* Accordion Body */}
                  {expandedId === (q.id || idx) && (
                    <div className="px-6 py-6 border-t border-gray-200 bg-gray-50 space-y-5">
                      
                      {/* Score Badge */}
                      <div>
                        <span className="inline-block bg-red-100 text-red-700 px-4 py-2 rounded-full text-sm font-bold">
                          Rating: {q.score}/100
                        </span>
                      </div>

                      {/* Your Answer Box */}
                      <div>
                        <label className="block text-sm font-bold text-gray-700 mb-3 uppercase tracking-wide">
                          Your Answer
                        </label>
                        <div className="bg-red-50 border border-red-200 rounded-lg p-5 text-gray-800 leading-relaxed">
                          {q.answer || 'No answer provided'}
                        </div>
                      </div>

                      {/* Correct Answer Box (Optional) */}
                      {q.correctAnswer && (
                        <div>
                          <label className="block text-sm font-bold text-gray-700 mb-3 uppercase tracking-wide">
                            Expected Answer
                          </label>
                          <div className="bg-green-50 border border-green-200 rounded-lg p-5 text-gray-800 leading-relaxed">
                            {q.correctAnswer}
                          </div>
                        </div>
                      )}

                      {/* Feedback Box */}
                      <div>
                        <label className="block text-sm font-bold text-gray-700 mb-3 uppercase tracking-wide">
                          Feedback
                        </label>
                        <div className="bg-blue-50 border border-blue-200 rounded-lg p-5 text-gray-800 leading-relaxed">
                          {q.feedback || 'No feedback available'}
                        </div>
                      </div>

                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action Button */}
        <div className="text-center">
          <button className="inline-block bg-blue-600 hover:bg-blue-700 text-white font-bold py-3 px-10 rounded-lg transition-colors shadow-md hover:shadow-lg">
            Back to Results
          </button>
        </div>

      </div>
    </div>
  );
};

export default InterviewFeedback;
